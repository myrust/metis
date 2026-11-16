"""Tests for ModelsRegistry (/api/models), BackupService (/api/backup/run), git approval, and allowed_paths."""

from __future__ import annotations

import os
import tarfile
import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from metis.automation.backup import BackupService
from metis.config import BackupConfig, MetisConfig
from metis.providers import models_registry as reg_mod
from metis.providers.base import BaseModelProvider, ProviderRequest, ProviderStreamEvent
from metis.providers.models_registry import ModelsRegistry, discover_gemini_models
from metis.providers.router import ProviderRouter
from metis.runtime.approval import is_sensitive_command
from metis.runtime.server import create_app
from metis.runtime.workspace import WorkspaceGuard, WorkspaceViolationError


class _NoopProvider(BaseModelProvider):
    name = "noop"

    def is_available(self) -> bool:
        return True

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        yield ProviderStreamEvent(kind="done", content="")


def test_git_destructive_commands_require_approval() -> None:
    assert is_sensitive_command("git push origin main") is True
    assert is_sensitive_command("git reset --hard HEAD~1") is True
    assert is_sensitive_command("git status -s") is False


def test_workspace_guard_allowed_paths(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    proj = tmp_path / "projects" / "app"
    proj.mkdir(parents=True)
    guard = WorkspaceGuard(ws, allowed_paths=[proj])

    resolved = guard.resolve_path(proj / "main.py")
    assert resolved == (proj / "main.py").resolve()

    with pytest.raises(WorkspaceViolationError):
        guard.resolve_path(tmp_path / "other" / "secret.txt")


def test_backup_service_skip_exclude_and_retention(tmp_path: Path) -> None:
    skipped = BackupService(BackupConfig(target_dir=None, source_dirs=(tmp_path,))).run_backup()
    assert skipped["status"] == "skipped"

    src = tmp_path / "src_ws"
    (src / "notes").mkdir(parents=True)
    (src / "notes" / "keep.txt").write_text("keep", encoding="utf-8")
    (src / "_refs").mkdir()
    (src / "_refs" / "skip.txt").write_text("skip", encoding="utf-8")
    (src / ".venv").mkdir()
    (src / ".venv" / "skip.txt").write_text("skip", encoding="utf-8")
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "skip.pyc").write_text("skip", encoding="utf-8")

    target = tmp_path / "mount_backup"
    target.mkdir()
    old_archive = target / "metis-backup-20200101T000000Z.tar.gz"
    old_archive.write_bytes(b"old")
    old_ts = time.time() - (10 * 86400)
    os.utime(old_archive, (old_ts, old_ts))

    svc = BackupService(BackupConfig(target_dir=target, source_dirs=(src,), retention_days=7))
    res = svc.run_backup()
    assert res["status"] == "completed"
    assert old_archive.name in res["pruned"]
    assert not old_archive.exists()

    archive_path = Path(res["archive"])
    assert archive_path.is_file()
    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
    assert any(n.endswith("keep.txt") for n in names)
    assert not any("_refs" in n or ".venv" in n or "__pycache__" in n for n in names)


def test_api_models_and_backup_endpoints(tmp_path: Path) -> None:
    target = tmp_path / "backup_mount"
    target.mkdir()
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "readme.txt").write_text("hello", encoding="utf-8")

    cfg = MetisConfig(
        home_dir=tmp_path / "home",
        workspace_dir=ws,
        graph_dir=tmp_path / "graph",
        skills_dir=tmp_path / "skills",
        skills_repo_dir=tmp_path / "skills_repo",
        config_file=tmp_path / "home" / "config.json",
        models_file=tmp_path / "home" / "models.json",
        backup=BackupConfig(target_dir=target, source_dirs=(ws,), retention_days=7),
    )
    app = create_app(config=cfg, router=ProviderRouter([_NoopProvider()]))
    client = TestClient(app)

    models_get = client.get("/api/models")
    assert models_get.status_code == 200
    assert any(p["id"] == "codex" for p in models_get.json()["providers"])

    models_post = client.post(
        "/api/models",
        json={
            "roles": {
                "memory_llm": {"provider_id": "qwen", "model": "qwen-turbo"},
            }
        },
    )
    assert models_post.status_code == 200
    assert models_post.json()["roles"]["memory_llm"]["model"] == "qwen-turbo"
    assert (tmp_path / "home" / "models.json").is_file()

    backup_res = client.post("/api/backup/run")
    assert backup_res.status_code == 200
    assert backup_res.json()["status"] == "completed"

    disc_res = client.get("/api/models/discover")
    assert disc_res.status_code == 200
    assert any(m["provider_id"] == "gemini" for m in disc_res.json()["models"])


@pytest.mark.asyncio
async def test_discover_gemini_models_and_router_hot_reload(monkeypatch, tmp_path: Path) -> None:
    class _FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "models": [
                    {
                        "name": "models/gemini-4-flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-4-pro",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/embedding-001",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                ]
            }

    class _FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def get(self, *_args, **_kwargs):
            return _FakeResp()

    monkeypatch.setattr(reg_mod.httpx, "AsyncClient", _FakeClient)
    found = await discover_gemini_models(api_key="fake-gemini-key")
    assert found == ["gemini-4-flash", "gemini-4-pro"]

    registry = ModelsRegistry(tmp_path / "models.json")
    registry.providers["gemini"].api_key = "fake-gemini-key"
    router = registry.build_provider_router()
    assert [p.name for p in router.candidates_for(provider_id="gemini")] == ["gemini"]
