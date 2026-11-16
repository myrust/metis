"""Tests for MetisConfig cross-platform resolution."""

from __future__ import annotations

import json
from pathlib import Path

from metis.config import MetisConfig


def test_config_defaults_and_env_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("METIS_HOME", str(tmp_path / "metis-home"))
    monkeypatch.delenv("METIS_WORKSPACE", raising=False)
    monkeypatch.delenv("METIS_GRAPH_DIR", raising=False)
    monkeypatch.delenv("METIS_PORT", raising=False)

    cfg = MetisConfig.load()
    assert cfg.home_dir == (tmp_path / "metis-home").resolve()
    assert cfg.workspace_dir == (tmp_path / "metis-home" / "workspace").resolve()
    assert cfg.graph_dir == (tmp_path / "metis-home" / "memory" / "graph").resolve()
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 9119
    assert not hasattr(cfg, "agy_bin")


def test_config_file_fallback_and_ensure_dirs(monkeypatch, tmp_path: Path) -> None:
    cfg_file = tmp_path / "custom.json"
    ws = tmp_path / "ws"
    graph = tmp_path / "graph"
    cfg_file.write_text(
        json.dumps(
            {
                "workspace_dir": str(ws),
                "graph_dir": str(graph),
                "port": 9220,
                "cron_enabled": True,
                "telegram_enabled": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("METIS_HOME", str(tmp_path / "home"))
    cfg = MetisConfig.load(config_path=cfg_file)
    cfg.ensure_directories()

    assert cfg.workspace_dir == ws.resolve()
    assert cfg.graph_dir == graph.resolve()
    assert cfg.port == 9220
    assert cfg.cron_enabled is True
    assert cfg.telegram_enabled is False
    assert cfg.memory.llm.model == "qwen-plus"
    assert cfg.memory.embedding.model == "text-embedding-v3"
    assert cfg.memory.vision.model == "qwen-vl-plus"
    assert ws.is_dir()
    assert graph.is_dir()


def test_config_memory_role_overrides(monkeypatch, tmp_path: Path) -> None:
    cfg_file = tmp_path / "mem.json"
    cfg_file.write_text(
        json.dumps(
            {
                "memory": {
                    "llm": {"base_url": "https://llm.local/v1", "api_key": "k1", "model": "qwen-turbo"},
                    "embedding": {"model": "text-embedding-v3"},
                    "vision": {"api_key": "k3", "model": "qwen-vl-max"},
                    "embedding_dim": 1536,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("METIS_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("METIS_MEMORY_EMBEDDING_API_KEY", "k2-env")

    cfg = MetisConfig.load(config_path=cfg_file)
    assert cfg.memory.llm.base_url == "https://llm.local/v1"
    assert cfg.memory.llm.model == "qwen-turbo"
    assert cfg.memory.embedding.api_key == "k2-env"
    assert cfg.memory.vision.model == "qwen-vl-max"
    assert cfg.memory.embedding_dim == 1536
