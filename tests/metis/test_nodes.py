"""Tests for NodeRouter, SSH/SFTP routing, and /api/nodes endpoints."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from metis.config import MetisConfig
from metis.providers.base import BaseModelProvider, ProviderRequest, ProviderStreamEvent
from metis.providers.router import ProviderRouter
from metis.runtime.nodes import NodeConfig, NodeRouter
from metis.runtime.server import create_app
from metis.runtime.workspace import WorkspaceViolationError


class _DummyProvider(BaseModelProvider):
    name = "dummy"

    def is_available(self) -> bool:
        return True

    async def stream(self, request: ProviderRequest):
        yield ProviderStreamEvent(kind="text_delta", content="ok")
        yield ProviderStreamEvent(kind="done", content="ok")


def test_node_router_defaults_and_persistence(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text('{"port": 9119}', encoding="utf-8")
    ws = tmp_path / "ws"
    router = NodeRouter(local_workspace=ws, config_file=config_file)

    assert router.active_node_id == "local"
    assert router.get_node().kind == "local"

    router.add_node(
        NodeConfig(
            id="gpu-box",
            kind="ssh",
            host="gpu.internal",
            workspace="/home/dev/ws",
            allowed_paths=["/home/dev/projects"],
            description="A100 node",
        )
    )
    router.activate("gpu-box")
    assert "gpu-box [active]" in router.render_prompt_index()

    reloaded = NodeRouter(local_workspace=ws, config_file=config_file)
    assert reloaded.active_node_id == "gpu-box"
    assert reloaded.get_node("gpu-box").host == "gpu.internal"
    assert reloaded.get_node("gpu-box").allowed_paths == ["/home/dev/projects"]
    assert '"port": 9119' in config_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_node_router_local_and_mocked_ssh(tmp_path: Path) -> None:
    router = NodeRouter(local_workspace=tmp_path / "ws", config_file=tmp_path / "config.json")
    await router.write_file("a.txt", "hello\nworld\n", node_id="local")
    assert await router.read_lines("a.txt", 1, 2, node_id="local") == "1: hello\n2: world"

    router.add_node(
        NodeConfig(
            id="remote",
            kind="ssh",
            host="remote-host",
            workspace="/srv/ws",
            allowed_paths=["/srv/projects"],
        )
    )

    mock_conn = MagicMock()
    mock_conn.is_closed.return_value = False
    mock_conn.run = AsyncMock(return_value=SimpleNamespace(stdout="remote-ok", stderr="", exit_status=0))
    router._ssh_pool["remote"] = mock_conn

    ok, out = await router.run_shell("uname -a", node_id="remote")
    assert ok is True
    assert out == "remote-ok"
    mock_conn.run.assert_awaited_once()
    called_cmd = mock_conn.run.call_args.args[0]
    assert called_cmd.startswith("cd /srv/ws && uname -a")

    assert (
        router._resolve_remote_path("/srv/ws", "/srv/projects/app.py", ["/srv/projects"])
        == "/srv/projects/app.py"
    )
    with pytest.raises(WorkspaceViolationError):
        router._resolve_remote_path("/srv/ws", "../../etc/passwd", ["/srv/projects"])


def test_api_nodes_crud_and_activate(tmp_path: Path) -> None:
    cfg = MetisConfig(
        home_dir=tmp_path / "home",
        workspace_dir=tmp_path / "ws",
        graph_dir=tmp_path / "graph",
        skills_dir=tmp_path / "skills",
    )
    app = create_app(config=cfg, router=ProviderRouter([_DummyProvider()]))
    client = TestClient(app)

    res = client.get("/api/nodes")
    assert res.status_code == 200
    assert res.json()["active_node_id"] == "local"

    add_res = client.post(
        "/api/nodes",
        json={"id": "nas", "host": "nas.local", "workspace": "/volume1/metis"},
    )
    assert add_res.status_code == 200

    act_res = client.post("/api/nodes/nas/activate")
    assert act_res.status_code == 200
    assert act_res.json()["active_node_id"] == "nas"

    del_local = client.delete("/api/nodes/local")
    assert del_local.status_code == 400

    del_nas = client.delete("/api/nodes/nas")
    assert del_nas.status_code == 200
    assert del_nas.json()["active_node_id"] == "local"
