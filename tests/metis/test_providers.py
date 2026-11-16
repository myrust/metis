"""Tests for Hephaestus providers and policy compliance."""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator

import pytest

from metis.providers import (
    AnthropicApiProvider,
    BaseModelProvider,
    CodexCliProvider,
    GeminiApiProvider,
    OpenAICompatProvider,
    ProviderRequest,
    ProviderRouter,
    ProviderStreamEvent,
)


class _FakeProvider(BaseModelProvider):
    def __init__(self, name: str, available: bool = True, fail: bool = False, reply: str = "ok") -> None:
        super().__init__()
        self.name = name
        self._available = available
        self._fail = fail
        self._reply = reply

    def is_available(self) -> bool:
        return self._available

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        if self._fail:
            yield ProviderStreamEvent(kind="error", content=f"{self.name} failed")
            return
        yield ProviderStreamEvent(kind="text_delta", content=self._reply)
        yield ProviderStreamEvent(kind="done", content=self._reply)


def test_agy_cli_provider_is_completely_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("metis.providers.agy_cli")


def test_codex_cli_provider_command_and_parse() -> None:
    provider = CodexCliProvider(binary_path="/usr/local/bin/codex")
    assert provider.is_available() is True
    cmd = provider._build_command(ProviderRequest(prompt="hello", system_prompt="sys", model="gpt-5"))
    assert cmd[:3] == ["/usr/local/bin/codex", "exec", "--json"]
    assert "--model" in cmd

    ev_think = CodexCliProvider._parse_line('{"type":"thinking","text":"step 1"}')
    assert ev_think is not None and ev_think.kind == "thinking"
    ev_item = CodexCliProvider._parse_line('{"type":"item.completed","item":{"text":"answer"}}')
    assert ev_item is not None and ev_item.kind == "text_delta" and ev_item.content == "answer"


def test_api_providers_availability(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert GeminiApiProvider().is_available() is False
    assert OpenAICompatProvider().is_available() is False
    assert AnthropicApiProvider().is_available() is False

    assert GeminiApiProvider(api_key="test-key").is_available() is True
    assert OpenAICompatProvider(api_key="test-key").is_available() is True
    assert AnthropicApiProvider(api_key="test-key").is_available() is True


@pytest.mark.asyncio
async def test_provider_router_fallback() -> None:
    failing = _FakeProvider("gemini-api", available=True, fail=True)
    backup = _FakeProvider("codex-cli", available=True, fail=False, reply="fallback-ok")
    router = ProviderRouter(
        providers=[failing, backup],
        task_routes={"code": ["gemini-api", "codex-cli"]},
    )
    result = await router.generate(ProviderRequest(prompt="test"), task_type="code")
    assert result == "fallback-ok"
