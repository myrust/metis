"""Tests for WorkspaceGuard, ApprovalGate, LoopCircuitBreaker, and FastAPI endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from metis.config import MetisConfig
from metis.providers.base import BaseModelProvider, ProviderRequest, ProviderStreamEvent
from metis.providers.router import ProviderRouter
from metis.runtime.agent import MetisAgentRunner
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
        assert "echo:User: hi" in body

    skills_resp = client.get("/api/skills")
    assert skills_resp.status_code == 200
    assert any(s["name"] == "system-health" for s in skills_resp.json()["skills"])

    skill_detail = client.get("/api/skills/system-health")
    assert skill_detail.status_code == 200
    assert "psutil" in skill_detail.json()["content"]

    assert client.get("/api/cron").json() == {"enabled": False, "jobs": []}

    guard = app.state.workspace
    guard.write_file("hello.txt", "line1\nline2\n")
    files_resp = client.get("/api/workspace/files")
    assert "hello.txt" in files_resp.json()["files"]

    read_resp = client.get("/api/workspace/read", params={"path": "hello.txt", "start_line": 2, "end_line": 2})
    assert read_resp.status_code == 200
    assert read_resp.json()["content"] == "2: line2"

    escape_resp = client.get("/api/workspace/read", params={"path": "../secret.txt"})
    assert escape_resp.status_code == 403


class _TwoStepToolProvider(BaseModelProvider):
    name = "two-step"

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def is_available(self) -> bool:
        return True

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        self.calls += 1
        if self.calls == 1:
            yield ProviderStreamEvent(
                kind="text_delta",
                content='<tool_call>{"name": "write_file", "args": {"path": "out.txt", "content": "ok"}}</tool_call>',
            )
        else:
            yield ProviderStreamEvent(kind="text_delta", content="Finished writing out.txt.")
        yield ProviderStreamEvent(kind="done", content="")


@pytest.mark.asyncio
async def test_agent_runner_tool_call_and_approval_flow(tmp_path: Path) -> None:
    ws = WorkspaceGuard(tmp_path / "ws")
    gate = ApprovalGate()
    runner = MetisAgentRunner(
        router=ProviderRouter([_TwoStepToolProvider()]),
        workspace=ws,
        approval_gate=gate,
    )

    events = []
    async for ev in runner.run_stream("write out.txt"):
        events.append(ev)
        if ev.event == "approval_required":
            gate.resolve(ev.data["approval_id"], True)

    event_types = [e.event for e in events]
    assert "tool_call" in event_types
    assert "approval_required" in event_types
    assert "tool_result" in event_types
    assert event_types[-1] == "done"
    assert (ws.root / "out.txt").read_text(encoding="utf-8") == "ok"
