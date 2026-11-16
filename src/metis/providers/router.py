"""ProviderRouter: Task-based routing and automatic fallback across Hephaestus providers."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence

from metis.providers.base import BaseModelProvider, ProviderRequest, ProviderStreamEvent

log = logging.getLogger(__name__)


class ProviderRouter:
    """Routes model requests to ordered providers with automatic fallback."""

    def __init__(
        self,
        providers: Sequence[BaseModelProvider],
        task_routes: dict[str, list[str]] | None = None,
    ) -> None:
        self._providers = {p.name: p for p in providers}
        self._order = [p.name for p in providers]
        self._task_routes = task_routes or {}

    def candidates_for(self, task_type: str | None = None) -> list[BaseModelProvider]:
        """Return ordered available providers for a given task_type."""
        names = self._task_routes.get(task_type, self._order) if task_type else self._order
        ordered: list[BaseModelProvider] = []
        for name in names:
            provider = self._providers.get(name)
            if provider is not None and provider.is_available():
                ordered.append(provider)
        for name in self._order:
            provider = self._providers[name]
            if provider not in ordered and provider.is_available():
                ordered.append(provider)
        return ordered

    async def stream(
        self,
        request: ProviderRequest,
        task_type: str | None = None,
    ) -> AsyncIterator[ProviderStreamEvent]:
        """Stream from the first available provider, falling back on errors before output."""
        candidates = self.candidates_for(task_type)
        if not candidates:
            yield ProviderStreamEvent(
                kind="error",
                content="No available Hephaestus providers configured.",
            )
            return

        last_error = "All providers failed."
        for provider in candidates:
            emitted_output = False
            failed = False
            try:
                async for event in provider.stream(request):
                    if event.kind == "error":
                        last_error = event.content
                        failed = True
                        break
                    if event.kind in {"text_delta", "thinking"}:
                        emitted_output = True
                    yield event
                if not failed:
                    return
            except (RuntimeError, ValueError, OSError, TimeoutError) as exc:  # pragma: no cover - defensive fallback
                last_error = str(exc)
                log.warning("Provider %s failed: %s", provider.name, exc)
                if emitted_output:
                    yield ProviderStreamEvent(kind="error", content=last_error)
                    return

        yield ProviderStreamEvent(kind="error", content=last_error)

    async def generate(self, request: ProviderRequest, task_type: str | None = None) -> str:
        """Collect full text output using task routing and fallback."""
        chunks: list[str] = []
        async for event in self.stream(request, task_type=task_type):
            if event.kind == "text_delta":
                chunks.append(event.content)
            elif event.kind == "error":
                raise RuntimeError(event.content)
        return "".join(chunks)
