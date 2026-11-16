"""FastAPI + SSE server for the Metis backend (default 127.0.0.1:9119)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from metis.config import MetisConfig
from metis.providers.api_adapter import (
    AnthropicApiProvider,
    GeminiApiProvider,
    OpenAICompatProvider,
)
from metis.providers.base import ProviderRequest
from metis.providers.codex_cli import CodexCliProvider
from metis.providers.router import ProviderRouter
from metis.runtime.approval import ApprovalGate
from metis.runtime.events import RuntimeEvent
from metis.runtime.workspace import WorkspaceGuard


class ChatRequest(BaseModel):
    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    task_type: str | None = None


class ApprovalDecision(BaseModel):
    approval_id: str
    approved: bool


def build_default_router(config: MetisConfig) -> ProviderRouter:
    """Construct the Hephaestus ProviderRouter from MetisConfig."""
    return ProviderRouter(
        providers=[
            GeminiApiProvider(),
            OpenAICompatProvider(),
            AnthropicApiProvider(),
            CodexCliProvider(binary_path=config.codex_bin, workspace_dir=config.workspace_dir),
        ]
    )


def create_app(
    config: MetisConfig | None = None,
    router: ProviderRouter | None = None,
) -> FastAPI:
    """Create and configure the Metis FastAPI application."""
    cfg = config or MetisConfig.load()
    cfg.ensure_directories()

    app = FastAPI(title="Metis Backend", version="0.1.0")
    gate = ApprovalGate()
    workspace = WorkspaceGuard(cfg.workspace_dir)
    active_router = router or build_default_router(cfg)

    app.state.config = cfg
    app.state.approval_gate = gate
    app.state.workspace = workspace
    app.state.router = active_router

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "host": cfg.host,
            "port": cfg.port,
            "workspace": str(cfg.workspace_dir),
            "pending_approvals": len(gate.list_pending()),
        }

    @app.get("/api/approval")
    async def list_approvals() -> dict[str, Any]:
        return {"pending": gate.list_pending()}

    @app.post("/api/approval")
    async def submit_approval(decision: ApprovalDecision) -> dict[str, Any]:
        resolved = gate.resolve(decision.approval_id, decision.approved)
        if not resolved:
            raise HTTPException(status_code=404, detail="Unknown or already resolved approval_id")
        return {"approval_id": decision.approval_id, "approved": decision.approved}

    @app.post("/api/chat/stream")
    async def chat_stream(body: ChatRequest) -> EventSourceResponse:
        async def event_generator() -> AsyncIterator[dict[str, str]]:
            req = ProviderRequest(
                prompt=body.prompt,
                system_prompt=body.system_prompt,
                model=body.model,
            )
            full_text: list[str] = []
            async for ev in active_router.stream(req, task_type=body.task_type):
                if ev.kind == "thinking":
                    yield RuntimeEvent("thinking", {"content": ev.content}).to_sse_dict()
                elif ev.kind == "text_delta":
                    full_text.append(ev.content)
                    yield RuntimeEvent("thinking", {"delta": ev.content}).to_sse_dict()
                elif ev.kind == "error":
                    yield RuntimeEvent("done", {"error": ev.content}).to_sse_dict()
                    return
                elif ev.kind == "done":
                    yield RuntimeEvent(
                        "done",
                        {"content": "".join(full_text) or ev.content},
                    ).to_sse_dict()
                    return
            yield RuntimeEvent("done", {"content": "".join(full_text)}).to_sse_dict()

        return EventSourceResponse(event_generator())

    # Optional static frontend mount point (left empty in Phase 1).
    if cfg.static_dir and cfg.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(cfg.static_dir), html=True), name="static")

    return app


def main() -> None:
    """CLI entry point for running the Metis FastAPI server."""
    cfg = MetisConfig.load()
    uvicorn.run(create_app(cfg), host=cfg.host, port=cfg.port)
