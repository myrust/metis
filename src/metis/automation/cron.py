"""Lightweight Cron heartbeat scheduler (nanobot-inspired, gated by config.cron_enabled)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from croniter import croniter

log = logging.getLogger(__name__)

CronCallback = Callable[[str], Awaitable[None]]


@dataclass
class CronJob:
    """Scheduled recurring job definition."""

    name: str
    cron_expr: str
    callback: CronCallback
    enabled: bool = True
    next_run: datetime = field(init=False)

    def __post_init__(self) -> None:
        self.advance()

    def advance(self, base_time: datetime | None = None) -> None:
        now = base_time or datetime.now(UTC)
        self.next_run = croniter(self.cron_expr, now).get_next(datetime)


class CronHeartbeatService:
    """Runs scheduled jobs in an asyncio background loop when enabled."""

    def __init__(self, enabled: bool = False, poll_interval: float = 5.0) -> None:
        self.enabled = enabled
        self.poll_interval = poll_interval
        self._jobs: dict[str, CronJob] = {}
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def register(self, name: str, cron_expr: str, callback: CronCallback) -> None:
        """Register or replace a cron job."""
        self._jobs[name] = CronJob(name=name, cron_expr=cron_expr, callback=callback)

    def unregister(self, name: str) -> None:
        self._jobs.pop(name, None)

    def list_jobs(self) -> list[str]:
        return list(self._jobs.keys())

    async def tick(self, now: datetime | None = None) -> list[str]:
        """Execute all due jobs once; returns names of jobs triggered."""
        if not self.enabled:
            return []
        current = now or datetime.now(UTC)
        triggered: list[str] = []
        for job in list(self._jobs.values()):
            if job.enabled and current >= job.next_run:
                try:
                    await job.callback(job.name)
                    triggered.append(job.name)
                except Exception:  # pragma: no cover
                    log.exception("Cron job %s failed", job.name)
                finally:
                    job.advance(current)
        return triggered

    async def start(self) -> None:
        """Start the background heartbeat loop if enabled."""
        if not self.enabled or self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop(), name="metis-cron-heartbeat")

    async def stop(self) -> None:
        """Stop the background heartbeat loop."""
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            await self.tick()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval)
            except TimeoutError:
                continue
