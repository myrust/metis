"""Base abstractions for the Hephaestus model provider layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ProviderRequest:
    """Unified invocation payload across CLI and HTTP API providers."""

    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    max_tokens: int = 4096
    temperature: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderStreamEvent:
    """Normalized streaming event emitted by any BaseModelProvider."""

    kind: str  # "thinking" | "text_delta" | "done" | "error"
    content: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class UsageRecorderHook(Protocol):
    """Optional extension hook reserved for future usage/quota accounting."""

    def on_invocation_start(self, provider_name: str, request: ProviderRequest) -> None:
        """Called before a provider invocation begins."""

    def on_invocation_end(
        self,
        provider_name: str,
        request: ProviderRequest,
        usage: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        """Called after a provider invocation completes or fails."""


class BaseModelProvider(ABC):
    """Unified abstract base class for all Hephaestus model providers."""

    name: str = "base"

    def __init__(self, usage_hook: UsageRecorderHook | None = None) -> None:
        self.usage_hook = usage_hook

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider binary or credentials are ready."""

    @abstractmethod
    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        """Stream normalized ProviderStreamEvent items for the given request."""
        raise NotImplementedError
        yield  # pragma: no cover

    async def generate(self, request: ProviderRequest) -> str:
        """Collect streamed text_delta events into a single response string."""
        chunks: list[str] = []
        if self.usage_hook is not None:
            self.usage_hook.on_invocation_start(self.name, request)
        err: Exception | None = None
        try:
            async for event in self.stream(request):
                if event.kind == "text_delta":
                    chunks.append(event.content)
                elif event.kind == "error":
                    raise RuntimeError(event.content or f"{self.name} provider error")
            return "".join(chunks)
        except Exception as exc:
            err = exc
            raise
        finally:
            if self.usage_hook is not None:
                self.usage_hook.on_invocation_end(self.name, request, usage=None, error=err)
