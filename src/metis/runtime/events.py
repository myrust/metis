"""SSE event definitions for the Metis runtime."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

EventType = Literal["thinking", "tool_call", "tool_result", "approval_required", "done"]


@dataclass(frozen=True)
class RuntimeEvent:
    """Structured event emitted over the FastAPI SSE stream."""

    event: EventType
    data: dict[str, Any] = field(default_factory=dict)

    def to_sse_dict(self) -> dict[str, str]:
        """Return a dict compatible with sse-starlette EventSourceResponse."""
        return {"event": self.event, "data": json.dumps(self.data, ensure_ascii=False)}

    def to_wire(self) -> str:
        """Format as standard SSE wire text."""
        payload = asdict(self)
        return f"event: {self.event}\ndata: {json.dumps(payload['data'], ensure_ascii=False)}\n\n"
