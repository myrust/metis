"""Tests for system metrics, usage/cost tracker, todos, ideas, custom charts, and cron API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi.testclient import TestClient

from metis.config import MetisConfig
from metis.providers.base import BaseModelProvider, ProviderRequest, ProviderStreamEvent
from metis.providers.router import ProviderRouter
from metis.runtime.server import create_app
from metis.runtime.system_metrics import collect_system_metrics
from metis.runtime.usage import UsageTracker


class _EchoModel(BaseModelProvider):
    name = "echo"

    def is_available(self) -> bool:
        return True

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        yield ProviderStreamEvent(kind="text_delta", content="reply")
        yield ProviderStreamEvent(kind="done", content="reply")


def test_collect_system_metrics() -> None:
    metrics = collect_system_metrics(top_n=5)
    assert 0.0 <= metrics["cpu_percent"] <= 100.0
    assert 0.0 <= metrics["memory_percent"] <= 100.0
    assert 0.0 <= metrics["disk_percent"] <= 100.0
    assert metrics["process_count"] >= 1
    assert "read_mb" in metrics["disk_io"]
    assert len(metrics["top_processes"]) <= 5


def test_usage_tracker_summary(tmp_path: Path) -> None:
    tracker = UsageTracker(tmp_path / "usage.jsonl")
    tracker.record_completion(
        provider_name="gemini",
        model="gemini-4-flash",
        prompt_text="hello " * 100,
        output_text="world " * 50,
    )
    summary = tracker.summary(days=7)
    assert summary["total_calls"] == 1
    assert summary["total_input_tokens"] > 0
    assert summary["total_output_tokens"] > 0
    assert summary["total_cost_usd"] > 0.0
    assert "gemini-4-flash" in summary["by_model"]


def test_workbench_endpoints(tmp_path: Path) -> None:
    cfg = MetisConfig(
        home_dir=tmp_path / "home",
        workspace_dir=tmp_path / "ws",
        graph_dir=tmp_path / "graph",
        skills_dir=tmp_path / "skills",
        skills_repo_dir=tmp_path / "skills_repo",
        config_file=tmp_path / "home" / "config.json",
        models_file=tmp_path / "home" / "models.json",
    )
    app = create_app(config=cfg, router=ProviderRouter([_EchoModel()]))
    client = TestClient(app)

    sys_res = client.get("/api/system/metrics")
    assert sys_res.status_code == 200
    assert sys_res.json()["process_count"] >= 1

    todo = client.post("/api/todos", json={"title": "Test Metis", "priority": "high"}).json()
    assert len(client.get("/api/todos").json()["todos"]) == 1
    toggled = client.patch(f"/api/todos/{todo['id']}", json={"done": True}).json()
    assert toggled["done"] is True
    assert client.delete(f"/api/todos/{todo['id']}").status_code == 200

    idea = client.post("/api/ideas", json={"title": "Voice mode", "tag": "ui"}).json()
    assert len(client.get("/api/ideas").json()["ideas"]) == 1
    assert client.delete(f"/api/ideas/{idea['id']}").status_code == 200

    chart = client.post(
        "/api/charts",
        json={"title": "Weekly", "chart_type": "ring", "labels": ["A", "B"], "values": [30, 70]},
    ).json()
    assert len(client.get("/api/charts").json()["charts"]) == 1
    assert client.delete(f"/api/charts/{chart['id']}").status_code == 200

    cron_add = client.post("/api/cron", json={"name": "ping", "cron_expr": "0 * * * *", "prompt": ""})
    assert cron_add.status_code == 200
    assert "ping" in cron_add.json()["jobs"]
    assert client.post("/api/cron/ping/run").status_code == 200
    assert client.delete("/api/cron/ping").status_code == 200

    assert client.get("/api/memory/stats").status_code == 200
    assert client.get("/api/usage/summary").status_code == 200
