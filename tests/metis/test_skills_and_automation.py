"""Tests for progressive SKILL.md loader, distiller, CronHeartbeatService, and TelegramGateway."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from metis.automation.cron import CronHeartbeatService
from metis.automation.telegram import TelegramGateway
from metis.skills_engine.distiller import SkillDistiller
from metis.skills_engine.loader import SkillRegistry

REPO_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"


def test_builtin_skills_progressive_disclosure() -> None:
    registry = SkillRegistry([REPO_SKILLS_DIR])
    names = {s.name for s in registry.list_summaries()}
    assert {"deepcode-plan-verify", "system-health", "workspace-backup"} <= names

    index_text = registry.render_prompt_index()
    assert "system-health" in index_text
    assert "psutil.cpu_percent" not in index_text  # Body must NOT be in prompt index

    full_body = registry.load_skill("system-health")
    assert "psutil.cpu_percent" in full_body


@pytest.mark.asyncio
async def test_skill_distiller_fallback(tmp_path: Path) -> None:
    distiller = SkillDistiller(skills_dir=tmp_path)
    out = await distiller.distill_from_messages(
        skill_name="Check Logs",
        description="Inspect recent service logs.",
        transcript=["Locate log file", "Grep for ERROR"],
    )
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "name: check-logs" in text
    assert "Locate log file" in text


@pytest.mark.asyncio
async def test_cron_heartbeat_gating_and_tick() -> None:
    ran: list[str] = []

    async def _job(name: str) -> None:
        ran.append(name)

    disabled = CronHeartbeatService(enabled=False)
    disabled.register("health", "* * * * *", _job)
    future = datetime.now(UTC) + timedelta(minutes=5)
    assert await disabled.tick(now=future) == []
    assert ran == []

    enabled = CronHeartbeatService(enabled=True)
    enabled.register("health", "* * * * *", _job)
    triggered = await enabled.tick(now=future)
    assert triggered == ["health"]
    assert ran == ["health"]


def test_telegram_gateway_gating_and_allowlist() -> None:
    gw_disabled = TelegramGateway(enabled=False, token="123:abc")
    assert gw_disabled.build_application() is None

    gw_allow = TelegramGateway(enabled=True, token="123:abc", allowed_user_ids={42})
    assert gw_allow.is_authorized(42) is True
    assert gw_allow.is_authorized(99) is False
