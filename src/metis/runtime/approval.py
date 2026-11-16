"""Human-in-the-loop approval gate and anti-loop circuit breaker (OpenHands-inspired)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

_SENSITIVE_SHELL_PATTERNS = (
    re.compile(r"\brm\s+-[^\n]*r[^\n]*f", re.IGNORECASE),
    re.compile(r"\bsudo\b", re.IGNORECASE),
    re.compile(r"\b(mkfs|dd|fdisk|shutdown|reboot)\b", re.IGNORECASE),
    re.compile(r"\bchmod\s+-R\b", re.IGNORECASE),
    re.compile(r"(curl|wget)[^\n]*\|\s*(sh|bash|zsh)", re.IGNORECASE),
)


def is_sensitive_command(command: str) -> bool:
    """Return True if a shell command matches sensitive/destructive patterns."""
    return any(pattern.search(command) for pattern in _SENSITIVE_SHELL_PATTERNS)


@dataclass
class PendingApproval:
    """Represents a suspended tool/action waiting for user confirmation."""

    approval_id: str
    action_type: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    _future: asyncio.Future[bool] = field(default_factory=lambda: asyncio.get_running_loop().create_future())

    def resolve(self, approved: bool) -> None:
        if not self._future.done():
            self._future.set_result(approved)

    async def wait(self, timeout: float | None = None) -> bool:
        if timeout is not None:
            return await asyncio.wait_for(self._future, timeout=timeout)
        return await self._future


class ApprovalGate:
    """Manages pending human approvals exposed via /api/approval."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingApproval] = {}

    def requires_approval(self, action_type: str, details: dict[str, Any]) -> bool:
        """Determine whether an action must pause for human approval."""
        if action_type == "file_write":
            return True
        if action_type == "shell":
            return is_sensitive_command(str(details.get("command", "")))
        return action_type == "circuit_breaker"

    def create_request(
        self,
        action_type: str,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> PendingApproval:
        approval_id = uuid.uuid4().hex[:12]
        req = PendingApproval(
            approval_id=approval_id,
            action_type=action_type,
            summary=summary,
            details=details or {},
        )
        self._pending[approval_id] = req
        return req

    def resolve(self, approval_id: str, approved: bool) -> bool:
        """Resolve a pending approval request; returns False if unknown."""
        req = self._pending.pop(approval_id, None)
        if req is None:
            return False
        req.resolve(approved)
        return True

    def list_pending(self) -> list[dict[str, Any]]:
        return [
            {
                "approval_id": req.approval_id,
                "action_type": req.action_type,
                "summary": req.summary,
                "details": req.details,
            }
            for req in self._pending.values()
        ]


class LoopCircuitBreaker:
    """Trips when identical errors or repeated identical tool calls occur N times in a row."""

    def __init__(self, threshold: int = 3) -> None:
        if threshold < 1:
            raise ValueError("threshold must be >= 1")
        self.threshold = threshold
        self._last_call_sig: str | None = None
        self._call_streak: int = 0
        self._last_error: str | None = None
        self._error_streak: int = 0

    @staticmethod
    def _signature(tool_name: str, args: dict[str, Any]) -> str:
        canonical = json.dumps({"tool": tool_name, "args": args}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def record_call(self, tool_name: str, args: dict[str, Any]) -> bool:
        """Record a tool call; returns True if circuit breaker trips."""
        sig = self._signature(tool_name, args)
        if sig == self._last_call_sig:
            self._call_streak += 1
        else:
            self._last_call_sig = sig
            self._call_streak = 1
        return self._call_streak >= self.threshold

    def record_error(self, error_message: str | None) -> bool:
        """Record a tool/execution error; returns True if circuit breaker trips."""
        if not error_message:
            self._last_error = None
            self._error_streak = 0
            return False
        normalized = error_message.strip()
        if normalized == self._last_error:
            self._error_streak += 1
        else:
            self._last_error = normalized
            self._error_streak = 1
        return self._error_streak >= self.threshold

    def reset(self) -> None:
        self._last_call_sig = None
        self._call_streak = 0
        self._last_error = None
        self._error_streak = 0
