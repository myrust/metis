"""CodexCliProvider: Subprocess bridge to the system `codex exec` CLI."""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from metis.providers.base import (
    BaseModelProvider,
    ProviderRequest,
    ProviderStreamEvent,
    UsageRecorderHook,
)


class CodexCliProvider(BaseModelProvider):
    """Subprocess provider wrapping `codex exec`."""

    name: str = "codex-cli"

    def __init__(
        self,
        binary_path: str | None = None,
        workspace_dir: Path | None = None,
        timeout_seconds: float = 300.0,
        usage_hook: UsageRecorderHook | None = None,
    ) -> None:
        super().__init__(usage_hook=usage_hook)
        self._binary_path = binary_path or shutil.which("codex")
        self._workspace_dir = workspace_dir
        self._timeout_seconds = timeout_seconds

    @property
    def binary_path(self) -> str | None:
        """Resolved path to the `codex` executable."""
        return self._binary_path or shutil.which("codex")

    def is_available(self) -> bool:
        """Return True when the `codex` CLI executable is discoverable."""
        return self.binary_path is not None

    def _build_command(self, request: ProviderRequest) -> list[str]:
        exe = self.binary_path
        if not exe:
            raise FileNotFoundError("`codex` CLI binary not found in PATH or METIS_CODEX_BIN.")
        prompt = request.prompt
        if request.system_prompt:
            prompt = f"{request.system_prompt}\n\n{request.prompt}"
        cmd = [exe, "exec", "--json", prompt]
        if request.model:
            cmd.extend(["--model", request.model])
        return cmd

    @staticmethod
    def _parse_line(raw_line: str) -> ProviderStreamEvent | None:
        line = raw_line.strip()
        if not line:
            return None
        try:
            payload: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            return ProviderStreamEvent(kind="text_delta", content=raw_line)

        event_type = str(payload.get("type", "")).lower()
        if event_type in {"reasoning", "thinking"}:
            return ProviderStreamEvent(
                kind="thinking",
                content=str(payload.get("text") or payload.get("content") or ""),
                raw=payload,
            )
        if event_type in {"error", "turn.failed"}:
            err_msg = payload.get("message") or payload.get("error") or "codex exec error"
            return ProviderStreamEvent(kind="error", content=str(err_msg), raw=payload)
        if event_type in {"turn.completed", "done", "complete"}:
            return ProviderStreamEvent(
                kind="done",
                content=str(payload.get("result") or payload.get("content") or ""),
                raw=payload,
            )

        item = payload.get("item")
        if isinstance(item, dict) and item.get("text"):
            return ProviderStreamEvent(kind="text_delta", content=str(item["text"]), raw=payload)

        text = payload.get("delta") or payload.get("text") or payload.get("content") or ""
        return ProviderStreamEvent(kind="text_delta", content=str(text), raw=payload) if text else None

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        """Execute `codex exec` and yield normalized ProviderStreamEvent items."""
        cmd = self._build_command(request)
        cwd = str(self._workspace_dir) if self._workspace_dir else None

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        assert proc.stdout is not None
        assert proc.stderr is not None

        emitted_done = False
        try:
            while True:
                line_bytes = await asyncio.wait_for(
                    proc.stdout.readline(),
                    timeout=self._timeout_seconds,
                )
                if not line_bytes:
                    break
                event = self._parse_line(line_bytes.decode("utf-8", errors="replace"))
                if event is not None:
                    if event.kind == "done":
                        emitted_done = True
                    yield event

            return_code = await asyncio.wait_for(proc.wait(), timeout=10.0)
            if return_code != 0:
                stderr_text = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
                yield ProviderStreamEvent(
                    kind="error",
                    content=stderr_text or f"codex exec exited with status {return_code}",
                    raw={"returncode": return_code},
                )
            elif not emitted_done:
                yield ProviderStreamEvent(kind="done", content="", raw={"returncode": 0})
        except TimeoutError:
            proc.kill()
            await proc.wait()
            yield ProviderStreamEvent(
                kind="error",
                content=f"codex exec timed out after {self._timeout_seconds}s",
            )
