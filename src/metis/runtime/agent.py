"""End-to-end Metis agent execution loop with guardrails, approval gate, and tools."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from metis.providers.base import ProviderRequest
from metis.providers.router import ProviderRouter
from metis.runtime.approval import ApprovalGate, LoopCircuitBreaker
from metis.runtime.events import RuntimeEvent
from metis.runtime.nodes import NodeRouter
from metis.runtime.workspace import WorkspaceGuard, WorkspaceViolationError
from metis.skills_engine.loader import SkillRegistry

_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)

_SYSTEM_PREAMBLE = """You are Metis, a cross-platform personal AI workbench assistant.
When you need to use a tool, emit a single block in this exact format:
<tool_call>{"name": "<tool_name>", "args": {<json_args>}}</tool_call>

Available tools (pass optional "node_id" to target a specific node, otherwise the [active] node is used):
- list_files: {"subdir": ".", "node_id": "local"}
- read_file: {"path": "<rel_path>", "start_line": 1, "end_line": 200, "node_id": "local"}
- write_file: {"path": "<rel_path>", "content": "<text>", "node_id": "local"}
- edit_diff: {"path": "<rel_path>", "target": "<exact_snippet>", "replacement": "<new_text>", "node_id": "local"}
- run_shell: {"command": "<shell_cmd>", "node_id": "local"}
- load_skill: {"name": "<skill_name>"}

If no tool is needed, reply directly to the user."""


class MetisAgentRunner:
    """Runs multi-step tool-use turns with ApprovalGate and LoopCircuitBreaker."""

    def __init__(
        self,
        router: ProviderRouter,
        workspace: WorkspaceGuard,
        approval_gate: ApprovalGate,
        skills: SkillRegistry | None = None,
        node_router: NodeRouter | None = None,
        max_steps: int = 10,
        approval_timeout: float = 300.0,
    ) -> None:
        self.router = router
        self.workspace = workspace
        self.approval_gate = approval_gate
        self.skills = skills
        self.node_router = node_router or NodeRouter(
            local_workspace=workspace.root,
            nodes_file=workspace.root.parent / "nodes.yaml",
        )
        self.max_steps = max_steps
        self.approval_timeout = approval_timeout

    def _build_system_prompt(self, extra_system: str | None) -> str:
        parts = [_SYSTEM_PREAMBLE, self.node_router.render_prompt_index()]
        if self.skills is not None:
            index = self.skills.render_prompt_index()
            if index:
                parts.append(index)
        if extra_system:
            parts.append(extra_system)
        return "\n\n".join(parts)

    async def _require_approval(
        self,
        action_type: str,
        summary: str,
        details: dict[str, Any],
    ) -> tuple[RuntimeEvent, Any]:
        req = self.approval_gate.create_request(
            action_type=action_type,
            summary=summary,
            details=details,
        )
        event = RuntimeEvent(
            "approval_required",
            {
                "approval_id": req.approval_id,
                "action_type": req.action_type,
                "summary": req.summary,
                "details": req.details,
            },
        )
        return event, req

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> tuple[bool, str]:
        """Execute a single workspace/skill/shell tool via NodeRouter; returns (ok, output)."""
        node_id = str(args["node_id"]) if args.get("node_id") else None
        try:
            if name == "list_files":
                return await self.node_router.list_files(
                    subdir=str(args.get("subdir", ".")),
                    node_id=node_id,
                )

            if name == "read_file":
                out = await self.node_router.read_lines(
                    path=str(args["path"]),
                    start_line=int(args.get("start_line", 1)),
                    end_line=int(args["end_line"]) if args.get("end_line") is not None else None,
                    node_id=node_id,
                )
                return True, out

            if name == "write_file":
                msg = await self.node_router.write_file(
                    path=str(args["path"]),
                    content=str(args["content"]),
                    node_id=node_id,
                )
                return True, msg

            if name == "edit_diff":
                msg = await self.node_router.apply_diff(
                    path=str(args["path"]),
                    target_snippet=str(args["target"]),
                    replacement=str(args["replacement"]),
                    node_id=node_id,
                )
                return True, msg

            if name == "load_skill":
                if self.skills is None:
                    return False, "SkillRegistry is not configured."
                return True, self.skills.load_skill(str(args["name"]))

            if name == "run_shell":
                return await self.node_router.run_shell(
                    command=str(args["command"]),
                    node_id=node_id,
                )

            return False, f"Unknown tool: {name}"
        except (KeyError, ValueError, OSError, WorkspaceViolationError, TimeoutError) as exc:
            return False, f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _parse_tool_call(text: str) -> tuple[str, dict[str, Any]] | None:
        match = _TOOL_CALL_RE.search(text)
        if not match:
            return None
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict) or "name" not in payload:
            return None
        args = payload.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        return str(payload["name"]), args

    async def run_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        task_type: str | None = None,
    ) -> AsyncIterator[RuntimeEvent]:
        """Run the agent loop and yield RuntimeEvent items for SSE."""
        breaker = LoopCircuitBreaker(threshold=3)
        full_system = self._build_system_prompt(system_prompt)
        history: list[str] = [f"User: {prompt}"]

        for _step in range(self.max_steps):
            req = ProviderRequest(
                prompt="\n\n".join(history),
                system_prompt=full_system,
                model=model,
            )
            step_chunks: list[str] = []
            async for ev in self.router.stream(req, task_type=task_type):
                if ev.kind == "thinking":
                    yield RuntimeEvent("thinking", {"content": ev.content})
                elif ev.kind == "text_delta":
                    step_chunks.append(ev.content)
                    yield RuntimeEvent("thinking", {"delta": ev.content})
                elif ev.kind == "error":
                    yield RuntimeEvent("done", {"error": ev.content})
                    return

            reply = "".join(step_chunks)
            parsed = self._parse_tool_call(reply)
            if parsed is None:
                yield RuntimeEvent("done", {"content": reply})
                return

            tool_name, tool_args = parsed
            yield RuntimeEvent("tool_call", {"name": tool_name, "args": tool_args})

            # 1. Anti-loop circuit breaker check (repeated identical tool calls)
            if breaker.record_call(tool_name, tool_args):
                ap_ev, ap_req = await self._require_approval(
                    action_type="circuit_breaker",
                    summary=f"Circuit breaker tripped: repeated call to {tool_name}",
                    details={"name": tool_name, "args": tool_args},
                )
                yield ap_ev
                if not await ap_req.wait(timeout=self.approval_timeout):
                    yield RuntimeEvent("done", {"error": "Aborted by circuit breaker rejection."})
                    return
                breaker.reset()

            # 2. Sensitive action approval check
            gate_type = (
                "file_write"
                if tool_name in {"write_file", "edit_diff"}
                else ("shell" if tool_name == "run_shell" else tool_name)
            )
            if self.approval_gate.requires_approval(gate_type, tool_args):
                ap_ev, ap_req = await self._require_approval(
                    action_type=gate_type,
                    summary=f"Approve {tool_name}",
                    details=tool_args,
                )
                yield ap_ev
                approved = await ap_req.wait(timeout=self.approval_timeout)
                if not approved:
                    msg = f"Tool '{tool_name}' rejected by user."
                    yield RuntimeEvent("tool_result", {"name": tool_name, "ok": False, "output": msg})
                    history.append(f"Assistant: {reply}\nToolResult ({tool_name}): {msg}")
                    continue

            # 3. Execute tool
            ok, output = await self._execute_tool(tool_name, tool_args)
            yield RuntimeEvent("tool_result", {"name": tool_name, "ok": ok, "output": output})

            # 4. Anti-loop circuit breaker check (3 consecutive identical errors)
            if not ok and breaker.record_error(output):
                ap_ev, ap_req = await self._require_approval(
                    action_type="circuit_breaker",
                    summary=f"Circuit breaker tripped: repeated error in {tool_name}",
                    details={"name": tool_name, "error": output},
                )
                yield ap_ev
                if not await ap_req.wait(timeout=self.approval_timeout):
                    yield RuntimeEvent("done", {"error": "Aborted after repeated identical errors."})
                    return
                breaker.reset()
            elif ok:
                breaker.record_error(None)

            history.append(f"Assistant: {reply}\nToolResult ({tool_name}): {output}")

        yield RuntimeEvent("done", {"error": f"Reached max_steps ({self.max_steps})."})
