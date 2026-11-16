"""FastAPI + SSE server for the Metis backend (default 127.0.0.1:9119)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import httpx
import uvicorn
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from metis.automation.backup import BackupService
from metis.automation.cron import CronHeartbeatService
from metis.config import MetisConfig
from metis.memory.mnemosyne import MnemosyneMemory
from metis.providers.api_adapter import (
    AnthropicApiProvider,
    GeminiApiProvider,
    OpenAICompatProvider,
)
from metis.providers.codex_cli import CodexCliProvider
from metis.providers.models_registry import ModelsRegistry, discover_gemini_models
from metis.providers.router import ProviderRouter
from metis.runtime.agent import MetisAgentRunner
from metis.runtime.approval import ApprovalGate
from metis.runtime.nodes import NodeConfig, NodeRouter
from metis.runtime.system_metrics import collect_system_metrics
from metis.runtime.usage import UsageTracker
from metis.runtime.workbench_store import WorkbenchStore
from metis.runtime.workspace import WorkspaceGuard, WorkspaceViolationError
from metis.skills_engine.distiller import SkillDistiller
from metis.skills_engine.loader import SkillRegistry


class ChatRequest(BaseModel):
    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    task_type: str | None = None
    provider_id: str | None = None


class ApprovalDecision(BaseModel):
    approval_id: str
    approved: bool


class DistillSkillRequest(BaseModel):
    skill_name: str
    description: str
    transcript: list[str]


class MemoryIngestRequest(BaseModel):
    text: str | None = None
    file_path: str | None = None


class MemoryQueryRequest(BaseModel):
    question: str
    mode: str = "hybrid"


class NodeUpsertRequest(BaseModel):
    id: str
    kind: str = "ssh"
    host: str
    workspace: str
    allowed_paths: list[str] = []
    user: str | None = None
    port: int | None = None
    description: str = ""


class ModelsUpdateRequest(BaseModel):
    providers: list[dict[str, Any]] | None = None
    roles: dict[str, dict[str, Any]] | None = None


class TodoCreateRequest(BaseModel):
    title: str
    priority: str = "medium"


class TodoPatchRequest(BaseModel):
    done: bool | None = None


class IdeaCreateRequest(BaseModel):
    title: str
    content: str = ""
    tag: str = "general"


class ChartCreateRequest(BaseModel):
    title: str
    chart_type: str = "bar"
    labels: list[str]
    values: list[float]


class CronCreateRequest(BaseModel):
    name: str
    cron_expr: str
    prompt: str = ""


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


def _default_skill_dirs(config: MetisConfig) -> list[Path]:
    dirs: list[Path] = []
    repo_skills = Path(__file__).resolve().parents[3] / "skills"
    if repo_skills.is_dir():
        dirs.append(repo_skills)
    for candidate in (config.skills_dir, config.skills_repo_dir):
        if candidate not in dirs:
            dirs.append(candidate)
    return dirs


def create_app(
    config: MetisConfig | None = None,
    router: ProviderRouter | None = None,
    memory: MnemosyneMemory | None = None,
) -> FastAPI:
    """Create and configure the Metis FastAPI application."""
    cfg = config or MetisConfig.load()
    cfg.ensure_directories()

    models_file = (
        cfg.models_file
        if str(cfg.models_file) != "."
        else (cfg.home_dir / "models.json")
    )
    config_file = (
        cfg.config_file
        if str(cfg.config_file) != "."
        else (cfg.home_dir / "config.json")
    )
    skills_repo_dir = (
        cfg.skills_repo_dir
        if str(cfg.skills_repo_dir) != "."
        else cfg.skills_dir
    )

    models_registry = ModelsRegistry(models_file)
    gate = ApprovalGate()
    workspace = WorkspaceGuard(cfg.workspace_dir)
    node_router = NodeRouter(
        local_workspace=cfg.workspace_dir,
        config_file=config_file,
    )
    active_router = router or models_registry.build_provider_router(
        codex_bin=cfg.codex_bin,
        workspace_dir=cfg.workspace_dir,
    )
    custom_router_injected = router is not None
    skills = SkillRegistry(_default_skill_dirs(cfg))
    distiller = SkillDistiller(skills_repo_dir, provider=None)
    mnemosyne = memory or MnemosyneMemory(
        graph_dir=cfg.graph_dir,
        memory_config=models_registry.resolve_mnemosyne_config(cfg.memory),
    )
    data_dir = cfg.home_dir / "data"
    usage_tracker = UsageTracker(data_dir / "usage.jsonl")
    store = WorkbenchStore(data_dir)
    backup_service = BackupService(cfg.backup)
    cron = CronHeartbeatService(enabled=cfg.cron_enabled)

    async def _cron_backup(_job_name: str) -> None:
        backup_service.run_backup()

    if cfg.backup.target_dir is not None:
        cron.register("workspace-backup", cfg.backup.cron, _cron_backup)

    runner = MetisAgentRunner(
        router=active_router,
        workspace=workspace,
        approval_gate=gate,
        skills=skills,
        node_router=node_router,
        usage_tracker=usage_tracker,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await cron.start()
        try:
            yield
        finally:
            await cron.stop()
            await node_router.close_all()

    app = FastAPI(title="Metis Backend", version="0.1.0", lifespan=lifespan)

    app.state.config = cfg
    app.state.models_registry = models_registry
    app.state.approval_gate = gate
    app.state.workspace = workspace
    app.state.node_router = node_router
    app.state.router = active_router
    app.state.skills = skills
    app.state.memory = mnemosyne
    app.state.backup_service = backup_service
    app.state.usage_tracker = usage_tracker
    app.state.store = store
    app.state.cron = cron
    app.state.runner = runner

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "host": cfg.host,
            "port": cfg.port,
            "workspace": str(cfg.workspace_dir),
            "pending_approvals": len(gate.list_pending()),
            "skills_count": len(skills.list_summaries()),
            "cron_enabled": cfg.cron_enabled,
            "telegram_enabled": cfg.telegram_enabled,
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
            async for event in runner.run_stream(
                prompt=body.prompt,
                system_prompt=body.system_prompt,
                model=body.model,
                task_type=body.task_type,
                provider_id=body.provider_id,
            ):
                yield event.to_sse_dict()

        return EventSourceResponse(event_generator())

    @app.get("/api/skills")
    async def list_skills() -> dict[str, Any]:
        skills.refresh()
        return {
            "skills": [
                {"name": s.name, "description": s.description, "path": str(s.path)}
                for s in skills.list_summaries()
            ]
        }

    @app.get("/api/skills/{name}")
    async def get_skill(name: str) -> dict[str, str]:
        try:
            content = skills.load_skill(name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Skill '{name}' not found") from exc
        return {"name": name, "content": content}

    @app.post("/api/skills/distill")
    async def distill_skill(body: DistillSkillRequest) -> dict[str, str]:
        path = await distiller.distill_from_messages(
            skill_name=body.skill_name,
            description=body.description,
            transcript=body.transcript,
        )
        skills.refresh()
        return {"path": str(path)}

    @app.get("/api/workspace/files")
    async def list_workspace_files() -> dict[str, Any]:
        files = sorted(
            str(p.relative_to(workspace.root))
            for p in workspace.root.rglob("*")
            if p.is_file()
        )
        return {"workspace": str(workspace.root), "files": files}

    @app.get("/api/workspace/read")
    async def read_workspace_file(
        path: str = Query(...),
        start_line: int = Query(1, ge=1),
        end_line: int | None = Query(None, ge=1),
    ) -> dict[str, str]:
        try:
            content = workspace.read_lines(path, start_line=start_line, end_line=end_line)
        except WorkspaceViolationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"File not found: {path}") from exc
        return {"path": path, "content": content}

    @app.post("/api/memory/ingest")
    async def ingest_memory(body: MemoryIngestRequest) -> dict[str, str]:
        if body.text:
            await mnemosyne.ingest_text(body.text)
            return {"status": "ingested", "kind": "text"}
        if body.file_path:
            target = workspace.resolve_path(body.file_path)
            await mnemosyne.ingest_document(target)
            return {"status": "ingested", "kind": "document", "path": str(target)}
        raise HTTPException(status_code=400, detail="Either 'text' or 'file_path' is required")

    @app.post("/api/memory/query")
    async def query_memory(body: MemoryQueryRequest) -> dict[str, str]:
        answer = await mnemosyne.query(body.question, mode=body.mode)
        return {"question": body.question, "mode": body.mode, "answer": answer}

    @app.get("/api/cron")
    async def cron_status() -> dict[str, Any]:
        return {
            "enabled": cron.enabled,
            "jobs": cron.list_jobs(),
            "details": cron.jobs_detail(),
        }

    @app.post("/api/cron")
    async def add_cron_job(body: CronCreateRequest) -> dict[str, Any]:
        async def _custom_job(_name: str) -> None:
            if body.prompt:
                async for _ev in runner.run_stream(body.prompt):
                    pass

        cron.register(body.name, body.cron_expr, _custom_job)
        return {"jobs": cron.list_jobs(), "details": cron.jobs_detail()}

    @app.delete("/api/cron/{name}")
    async def delete_cron_job(name: str) -> dict[str, Any]:
        cron.unregister(name)
        return {"jobs": cron.list_jobs(), "details": cron.jobs_detail()}

    @app.post("/api/cron/{name}/run")
    async def trigger_cron_job(name: str) -> dict[str, str]:
        try:
            await cron.trigger_now(name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown cron job: {name}") from exc
        return {"status": "triggered", "name": name}

    @app.get("/api/system/metrics")
    async def system_metrics() -> dict[str, Any]:
        return collect_system_metrics()

    @app.get("/api/usage/summary")
    async def usage_summary(days: int = Query(7, ge=1, le=90)) -> dict[str, Any]:
        return usage_tracker.summary(days=days)

    @app.get("/api/todos")
    async def list_todos() -> dict[str, Any]:
        return {"todos": store.list_todos()}

    @app.post("/api/todos")
    async def create_todo(body: TodoCreateRequest) -> dict[str, Any]:
        return store.add_todo(body.title, priority=body.priority)

    @app.patch("/api/todos/{todo_id}")
    async def patch_todo(todo_id: str, body: TodoPatchRequest) -> dict[str, Any]:
        try:
            return store.toggle_todo(todo_id, done=body.done)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/todos/{todo_id}")
    async def remove_todo(todo_id: str) -> dict[str, str]:
        try:
            store.delete_todo(todo_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": todo_id}

    @app.get("/api/ideas")
    async def list_ideas() -> dict[str, Any]:
        return {"ideas": store.list_ideas()}

    @app.post("/api/ideas")
    async def create_idea(body: IdeaCreateRequest) -> dict[str, Any]:
        return store.add_idea(body.title, content=body.content, tag=body.tag)

    @app.delete("/api/ideas/{idea_id}")
    async def remove_idea(idea_id: str) -> dict[str, str]:
        try:
            store.delete_idea(idea_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": idea_id}

    @app.get("/api/charts")
    async def list_charts() -> dict[str, Any]:
        return {"charts": store.list_charts()}

    @app.post("/api/charts")
    async def create_chart(body: ChartCreateRequest) -> dict[str, Any]:
        return store.add_chart(
            title=body.title,
            chart_type=body.chart_type,
            labels=body.labels,
            values=body.values,
        )

    @app.delete("/api/charts/{chart_id}")
    async def remove_chart(chart_id: str) -> dict[str, str]:
        try:
            store.delete_chart(chart_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": chart_id}

    @app.get("/api/memory/stats")
    async def memory_stats() -> dict[str, Any]:
        files = sorted(
            p.name for p in mnemosyne.graph_dir.iterdir() if p.is_file()
        )
        return {"graph_dir": str(mnemosyne.graph_dir), "files_count": len(files), "files": files}

    @app.post("/api/memory/upload")
    async def upload_memory_file(file: Annotated[UploadFile, File()]) -> dict[str, str]:
        safe_name = Path(file.filename or "upload.txt").name
        dest = workspace.resolve_path(f"library/{safe_name}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(await file.read())
        await mnemosyne.ingest_document(dest)
        return {"status": "ingested", "filename": safe_name, "path": str(dest)}

    @app.get("/api/nodes")
    async def list_nodes() -> dict[str, Any]:
        return {
            "active_node_id": node_router.active_node_id,
            "nodes": [
                {
                    "id": n.id,
                    "kind": n.kind,
                    "host": n.host,
                    "workspace": n.workspace,
                    "allowed_paths": n.allowed_paths,
                    "user": n.user,
                    "port": n.port,
                    "description": n.description,
                }
                for n in node_router.list_nodes()
            ],
        }

    @app.post("/api/nodes")
    async def upsert_node(body: NodeUpsertRequest) -> dict[str, Any]:
        node = node_router.add_node(
            NodeConfig(
                id=body.id,
                kind=body.kind,
                host=body.host,
                workspace=body.workspace,
                allowed_paths=body.allowed_paths,
                user=body.user,
                port=body.port,
                description=body.description,
            )
        )
        return {
            "id": node.id,
            "kind": node.kind,
            "host": node.host,
            "workspace": node.workspace,
            "allowed_paths": node.allowed_paths,
        }

    @app.delete("/api/nodes/{node_id}")
    async def delete_node(node_id: str) -> dict[str, str]:
        try:
            await node_router.remove_node(node_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown node_id: {node_id}") from exc
        return {"deleted": node_id, "active_node_id": node_router.active_node_id}

    @app.post("/api/nodes/{node_id}/activate")
    async def activate_node(node_id: str) -> dict[str, str]:
        try:
            node = node_router.activate(node_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown node_id: {node_id}") from exc
        return {"active_node_id": node.id}

    @app.get("/api/models")
    async def get_models() -> dict[str, Any]:
        return models_registry.to_dict()

    @app.post("/api/models")
    async def update_models(body: ModelsUpdateRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if body.providers is not None:
            payload["providers"] = body.providers
        if body.roles is not None:
            payload["roles"] = body.roles
        models_registry.update_from_dict(payload)
        mnemosyne.memory_config = models_registry.resolve_mnemosyne_config(cfg.memory)
        if not custom_router_injected:
            refreshed = models_registry.build_provider_router(
                codex_bin=cfg.codex_bin,
                workspace_dir=cfg.workspace_dir,
            )
            runner.router = refreshed
            app.state.router = refreshed
        return models_registry.to_dict()

    @app.get("/api/models/discover")
    async def discover_models() -> dict[str, Any]:
        gemini_entry = models_registry.providers.get("gemini")
        live_gemini: list[str] = []
        discover_error: str | None = None
        try:
            live_gemini = await discover_gemini_models(
                api_key=gemini_entry.api_key if gemini_entry else None,
                base_url=gemini_entry.base_url if gemini_entry else None,
            )
        except (httpx.HTTPError, ValueError, OSError) as exc:  # pragma: no cover - network dependent
            discover_error = str(exc)

        options: list[dict[str, str]] = [
            {"provider_id": "gemini", "model": m} for m in live_gemini
        ]
        seen = {(o["provider_id"], o["model"]) for o in options}
        for entry in models_registry.providers.values():
            if entry.enabled and entry.default_model:
                key = (entry.id, entry.default_model)
                if key not in seen:
                    options.append({"provider_id": entry.id, "model": entry.default_model})
                    seen.add(key)
        return {"models": options, "error": discover_error}

    @app.post("/api/backup/run")
    async def run_backup_now() -> dict[str, Any]:
        try:
            return backup_service.run_backup()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    # Optional static frontend mount point (uses METIS_STATIC_DIR or built frontend/web/dist).
    default_dist = Path(__file__).resolve().parents[3] / "frontend" / "web" / "dist"
    static_root = cfg.static_dir if (cfg.static_dir and cfg.static_dir.is_dir()) else (
        default_dist if default_dist.is_dir() else None
    )
    if static_root is not None:
        app.mount("/", StaticFiles(directory=str(static_root), html=True), name="static")

    return app


def main() -> None:
    """CLI entry point for running the Metis FastAPI server."""
    cfg = MetisConfig.load()
    uvicorn.run(create_app(cfg), host=cfg.host, port=cfg.port)
