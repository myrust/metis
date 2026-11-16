"""Standard API Key protocol adapters: OpenAI-compatible, Google AI Studio Gemini, and Anthropic."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from metis.providers.base import (
    BaseModelProvider,
    ProviderRequest,
    ProviderStreamEvent,
    UsageRecorderHook,
)


class OpenAICompatProvider(BaseModelProvider):
    """Adapter for OpenAI and OpenAI-compatible Chat Completions APIs."""

    name: str = "openai-compat"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str = "gpt-4o-mini",
        usage_hook: UsageRecorderHook | None = None,
    ) -> None:
        super().__init__(usage_hook=usage_hook)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self._default_model = default_model

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        if not self._api_key:
            yield ProviderStreamEvent(kind="error", content="OPENAI_API_KEY is not configured.")
            return

        client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        kwargs: dict[str, Any] = {
            "model": request.model or self._default_model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "stream": True,
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature

        stream = await client.chat.completions.create(**kwargs)
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield ProviderStreamEvent(kind="text_delta", content=delta.content)
        yield ProviderStreamEvent(kind="done", content="")


class GeminiApiProvider(BaseModelProvider):
    """Adapter for Google AI Studio Gemini API Key (REST SSE)."""

    name: str = "gemini-api"
    _DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str = "gemini-2.5-flash",
        usage_hook: UsageRecorderHook | None = None,
    ) -> None:
        super().__init__(usage_hook=usage_hook)
        self._api_key = (
            api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        )
        self._base_url = (base_url or self._DEFAULT_BASE_URL).rstrip("/")
        self._default_model = default_model

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        if not self._api_key:
            yield ProviderStreamEvent(kind="error", content="GEMINI_API_KEY is not configured.")
            return

        model = request.model or self._default_model
        url = f"{self._base_url}/models/{model}:streamGenerateContent"
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
            "generationConfig": {"maxOutputTokens": request.max_tokens},
        }
        if request.system_prompt:
            body["systemInstruction"] = {"parts": [{"text": request.system_prompt}]}
        if request.temperature is not None:
            body["generationConfig"]["temperature"] = request.temperature

        async with httpx.AsyncClient(timeout=120.0) as client, client.stream(
            "POST",
            url,
            params={"alt": "sse", "key": self._api_key},
            json=body,
        ) as response:
            if response.status_code >= 400:
                err_body = (await response.aread()).decode("utf-8", errors="replace")
                yield ProviderStreamEvent(
                    kind="error",
                    content=f"Gemini API HTTP {response.status_code}: {err_body}",
                )
                return

            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    payload = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                for candidate in payload.get("candidates", []):
                    parts = candidate.get("content", {}).get("parts", [])
                    for part in parts:
                        text = part.get("text")
                        if text:
                            yield ProviderStreamEvent(kind="text_delta", content=text, raw=part)
        yield ProviderStreamEvent(kind="done", content="")


class AnthropicApiProvider(BaseModelProvider):
    """Adapter for Anthropic Messages API."""

    name: str = "anthropic-api"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str = "claude-sonnet-4-5",
        usage_hook: UsageRecorderHook | None = None,
    ) -> None:
        super().__init__(usage_hook=usage_hook)
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL")
        self._default_model = default_model

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        if not self._api_key:
            yield ProviderStreamEvent(kind="error", content="ANTHROPIC_API_KEY is not configured.")
            return

        client_kwargs: dict[str, Any] = {"api_key": self._api_key}
        if self._base_url:
            client_kwargs["base_url"] = self._base_url
        client = AsyncAnthropic(**client_kwargs)

        stream_kwargs: dict[str, Any] = {
            "model": request.model or self._default_model,
            "max_tokens": request.max_tokens,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system_prompt:
            stream_kwargs["system"] = request.system_prompt
        if request.temperature is not None:
            stream_kwargs["temperature"] = request.temperature

        async with client.messages.stream(**stream_kwargs) as stream:
            async for text in stream.text_stream:
                yield ProviderStreamEvent(kind="text_delta", content=text)
        yield ProviderStreamEvent(kind="done", content="")
