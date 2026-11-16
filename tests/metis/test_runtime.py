"""Tests for WorkspaceGuard, ApprovalGate, LoopCircuitBreaker, and FastAPI endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from metis.config import MetisConfig
from metis.providers.base import BaseModelProvider, ProviderRequest, ProviderStreamEvent
from metis.providers.router import ProviderRouter
from metis.runtime.approval import ApprovalGate, LoopCircuitBreaker, is_sensitive_command
from metis.runtime.server import create_app
from metis.runtime.workspace import WorkspaceGuard, WorkspaceViolationError


class _EchoProvider(BaseModelProvider):
    name = "echo"

    def is_available(self) -> bool:
        return True

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        yield ProviderStreamEvent(kind="thinking", content="analyzing")
        yield ProviderStreamEvent(kind="text_delta", content=f"echo:{request.prompt}")
        yield ProviderStreamEvent(kind="done", content="")


def test_workspace_guard_isolation_and_diff(tmp_path: Path) -> None:
    guard = WorkspaceGuard(tmp_path / "ws")
    guard.write_file("notes/todo.txt", "alpha\nbeta\ngamma\n")

    lines = guard.read_lines("notes/todo.txt", start_line=2, end_line=3)
    assert lines == "2: beta\n3: gamma"

    guard.apply_diff("notes/todo.txt", "beta", "BETA")
    assert "2: BETA" in guard.read_lines("notes/todo.txt", start_line=1, end_line=3)

    with pytest.raises(WorkspaceViolationError):
        guard.resolve_path("../outside.txt")


def test_circuit_breaker_trips_at_three() -> None:
    breaker = LoopCircuitBreaker(threshold=3)
    assert breaker.record_call("shell", {"cmd": "ls"}) is False
    assert breaker.record_call("shell", {"cmd": "ls"}) is False
    assert breaker.record_call("shell", {"cmd": "ls"}) is True

    breaker.reset()
    assert breaker.record_error("PermissionError") is False
    assert breaker.record_error("PermissionError") is False
    assert breaker.record_error("PermissionError") is True


def test_sensitive_command_detection() -> None:
    assert is_sensitive_command("rm -rf /tmp/foo") is True
    assert is_sensitive_command("sudo apt update") is True
    assert is_sensitive_command("ls -la") is False


@pytest.mark.asyncio
async def test_approval_gate_async_resolution() -> None:
    gate = ApprovalGate()
    assert gate.requires_approval("file_write", {"path": "a.py"}) is True
    req = gate.create_request("file_write", "Write a.py")
    assert len(gate.list_pending()) == 1
    assert gate.resolve(req.approval_id, True) is True
    assert await req.wait(timeout=1.0) is True


def test_fastapi_endpoints_and_sse(tmp_path: Path) -> None:
    cfg = MetisConfig(
        home_dir=tmp_path / "home",
        workspace_dir=tmp_path / "ws",
        graph_dir=tmp_path / "graph",
        skills_dir=tmp_path / "skills",
    )
    router = ProviderRouter([_EchoProvider()])
    app = create_app(config=cfg, router=router)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    missing = client.post("/api/approval", json={"approval_id": "none", "approved": True})
    assert missing.status_code == 404

    with client.stream("POST", "/api/chat/stream", json={"prompt": "hi"}) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
        assert "event: thinking" in body
        assert "event: done" in body
        assert "echo:hi" in body
