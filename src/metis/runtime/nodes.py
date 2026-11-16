"""Multi-node execution target router (local native + agentless SSH/SFTP via asyncssh).

Reads and persists `nodes` and `active_node_id` directly inside ~/.metis/config.json
with zero separate nodes config file.
"""

from __future__ import annotations

import asyncio
import json
import posixpath
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import asyncssh

from metis.runtime.workspace import WorkspaceGuard, WorkspaceViolationError


@dataclass
class NodeConfig:
    """Execution target definition (local or SSH host) with workspace and allowed_paths."""

    id: str
    kind: str = "ssh"  # "local" | "ssh"
    host: str = "localhost"
    workspace: str = "."
    allowed_paths: list[str] = field(default_factory=list)
    user: str | None = None
    port: int | None = None
    description: str = ""


class NodeRouter:
    """Routes file and shell operations to local WorkspaceGuard or pooled SSH/SFTP nodes."""

    def __init__(
        self,
        local_workspace: Path,
        config_file: Path,
        ssh_config_path: Path | None = None,
    ) -> None:
        self.local_workspace = Path(local_workspace).expanduser().resolve()
        self.config_file = Path(config_file).expanduser().resolve()
        self.ssh_config_path = (
            Path(ssh_config_path).expanduser().resolve()
            if ssh_config_path is not None
            else (Path.home() / ".ssh" / "config")
        )
        self._nodes: dict[str, NodeConfig] = {}
        self.active_node_id: str = "local"
        self.local_guard = WorkspaceGuard(self.local_workspace)
        self._ssh_pool: dict[str, asyncssh.SSHClientConnection] = {}
        self._pool_lock = asyncio.Lock()
        self.reload()

    def _ensure_local_node(self) -> None:
        if "local" not in self._nodes:
            self._nodes["local"] = NodeConfig(
                id="local",
                kind="local",
                host="localhost",
                workspace=str(self.local_workspace),
                allowed_paths=[str(self.local_workspace)],
                description="Local machine workspace",
            )
        local_node = self._nodes["local"]
        self.local_guard = WorkspaceGuard(
            Path(local_node.workspace),
            allowed_paths=local_node.allowed_paths,
        )

    def _read_config_json(self) -> dict[str, Any]:
        if not self.config_file.is_file():
            return {}
        try:
            data = json.loads(self.config_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def reload(self) -> None:
        """Load nodes and active_node_id from config.json, always preserving built-in local."""
        self._nodes = {}
        self.active_node_id = "local"
        raw = self._read_config_json()
        for item in raw.get("nodes", []):
            if isinstance(item, dict) and item.get("id"):
                ws = str(item.get("workspace", "~"))
                allowed = [str(p) for p in item.get("allowed_paths", []) if p]
                node = NodeConfig(
                    id=str(item["id"]),
                    kind=str(item.get("kind", "ssh")),
                    host=str(item.get("host", "localhost")),
                    workspace=ws,
                    allowed_paths=allowed,
                    user=item.get("user"),
                    port=int(item["port"]) if item.get("port") is not None else None,
                    description=str(item.get("description", "")),
                )
                self._nodes[node.id] = node
        if raw.get("active_node_id") in self._nodes:
            self.active_node_id = str(raw["active_node_id"])
        self._ensure_local_node()

    def save(self) -> None:
        """Persist nodes and active_node_id into config.json without clobbering other keys."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        raw = self._read_config_json()
        raw["active_node_id"] = self.active_node_id
        raw["nodes"] = [asdict(n) for n in self._nodes.values()]
        self.config_file.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def list_nodes(self) -> list[NodeConfig]:
        return list(self._nodes.values())

    def get_node(self, node_id: str | None = None) -> NodeConfig:
        target_id = node_id or self.active_node_id
        node = self._nodes.get(target_id)
        if node is None:
            raise KeyError(f"Unknown node_id: {target_id}")
        return node

    def add_node(self, node: NodeConfig) -> NodeConfig:
        self._nodes[node.id] = node
        if node.id == "local":
            self.local_guard = WorkspaceGuard(
                Path(node.workspace),
                allowed_paths=node.allowed_paths,
            )
        self.save()
        return node

    async def remove_node(self, node_id: str) -> None:
        if node_id == "local":
            raise ValueError("Cannot remove built-in 'local' node.")
        if node_id not in self._nodes:
            raise KeyError(f"Unknown node_id: {node_id}")
        self._nodes.pop(node_id)
        if self.active_node_id == node_id:
            self.active_node_id = "local"
        conn = self._ssh_pool.pop(node_id, None)
        if conn is not None:
            conn.close()
        self.save()

    def activate(self, node_id: str) -> NodeConfig:
        if node_id not in self._nodes:
            raise KeyError(f"Unknown node_id: {node_id}")
        self.active_node_id = node_id
        self.save()
        return self._nodes[node_id]

    def render_prompt_index(self) -> str:
        """Render available execution nodes for system prompt injection."""
        lines = ["Available Execution Nodes (pass optional `node_id` in file/shell tools):"]
        for node in self._nodes.values():
            marker = " [active]" if node.id == self.active_node_id else ""
            desc = f" — {node.description}" if node.description else ""
            allowed = f", allowed_paths={node.allowed_paths}" if node.allowed_paths else ""
            lines.append(
                f"- {node.id}{marker} ({node.kind}, host={node.host}, "
                f"workspace={node.workspace}{allowed}){desc}"
            )
        return "\n".join(lines)

    async def _get_ssh_conn(self, node: NodeConfig) -> asyncssh.SSHClientConnection:
        async with self._pool_lock:
            existing = self._ssh_pool.get(node.id)
            if existing is not None and not existing.is_closed():
                return existing

            connect_kwargs: dict[str, Any] = {}
            if self.ssh_config_path.is_file():
                connect_kwargs["config"] = [str(self.ssh_config_path)]
            if node.user:
                connect_kwargs["username"] = node.user
            if node.port is not None:
                connect_kwargs["port"] = node.port

            conn = await asyncssh.connect(node.host, **connect_kwargs)
            self._ssh_pool[node.id] = conn
            return conn

    async def close_all(self) -> None:
        for conn in self._ssh_pool.values():
            if not conn.is_closed():
                conn.close()
        self._ssh_pool.clear()

    @staticmethod
    def _resolve_remote_path(
        workspace: str,
        rel_or_abs: str,
        allowed_paths: list[str] | None = None,
    ) -> str:
        base = posixpath.normpath(workspace)
        candidate = (
            posixpath.normpath(rel_or_abs)
            if rel_or_abs.startswith("/")
            else posixpath.normpath(posixpath.join(base, rel_or_abs))
        )
        roots = [base, *[posixpath.normpath(p) for p in (allowed_paths or []) if p]]
        for root in roots:
            if candidate == root or candidate.startswith(root.rstrip("/") + "/"):
                return candidate
        raise WorkspaceViolationError(
            f"Remote path '{rel_or_abs}' escapes workspace '{workspace}' and allowed_paths."
        )

    async def run_shell(self, command: str, node_id: str | None = None) -> tuple[bool, str]:
        node = self.get_node(node_id)
        if node.kind == "local":
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(self.local_guard.root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=60.0)
            stdout = stdout_b.decode("utf-8", errors="replace").strip()
            stderr = stderr_b.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                return False, stderr or f"Command exited with {proc.returncode}"
            return True, stdout or "(no output)"

        conn = await self._get_ssh_conn(node)
        remote_cmd = f"cd {shlex.quote(node.workspace)} && {command}"
        result = await asyncio.wait_for(conn.run(remote_cmd, check=False), timeout=60.0)
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if result.exit_status != 0:
            return False, stderr or f"Remote command exited with {result.exit_status}"
        return True, stdout or "(no output)"

    async def list_files(self, subdir: str = ".", node_id: str | None = None) -> tuple[bool, str]:
        node = self.get_node(node_id)
        if node.kind == "local":
            target = self.local_guard.resolve_path(subdir)
            if not target.is_dir():
                return False, f"Directory not found: {subdir}"
            items = sorted(
                str(p.relative_to(self.local_guard.root))
                if p.is_relative_to(self.local_guard.root)
                else str(p)
                for p in target.rglob("*")
                if p.is_file()
            )
            return True, "\n".join(items) if items else "(empty)"

        remote_dir = self._resolve_remote_path(node.workspace, subdir, node.allowed_paths)
        conn = await self._get_ssh_conn(node)
        async with conn.start_sftp_client() as sftp:
            entries = await sftp.listdir(remote_dir)
            visible = sorted(e for e in entries if e not in {".", ".."})
            return True, "\n".join(visible) if visible else "(empty)"

    async def read_lines(
        self,
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
        node_id: str | None = None,
    ) -> str:
        node = self.get_node(node_id)
        if node.kind == "local":
            return self.local_guard.read_lines(path, start_line=start_line, end_line=end_line)

        remote_path = self._resolve_remote_path(node.workspace, path, node.allowed_paths)
        conn = await self._get_ssh_conn(node)
        async with conn.start_sftp_client() as sftp, sftp.open(remote_path, "r") as fh:
            content = await fh.read()
        lines = str(content).splitlines()
        total = len(lines)
        start = max(1, start_line)
        end = min(total, end_line) if end_line is not None else total
        if start > end and total > 0:
            return ""
        return "\n".join(f"{idx}: {lines[idx - 1]}" for idx in range(start, end + 1))

    async def write_file(self, path: str, content: str, node_id: str | None = None) -> str:
        node = self.get_node(node_id)
        if node.kind == "local":
            written = self.local_guard.write_file(path, content)
            return f"Wrote {written} on local"

        remote_path = self._resolve_remote_path(node.workspace, path, node.allowed_paths)
        conn = await self._get_ssh_conn(node)
        async with conn.start_sftp_client() as sftp:
            parent = posixpath.dirname(remote_path)
            if parent:
                await sftp.makedirs(parent, exist_ok=True)
            async with sftp.open(remote_path, "w") as fh:
                await fh.write(content)
        return f"Wrote {remote_path} on {node.id}"

    async def apply_diff(
        self,
        path: str,
        target_snippet: str,
        replacement: str,
        node_id: str | None = None,
    ) -> str:
        node = self.get_node(node_id)
        if node.kind == "local":
            edited = self.local_guard.apply_diff(path, target_snippet, replacement)
            return f"Updated {edited} on local"

        remote_path = self._resolve_remote_path(node.workspace, path, node.allowed_paths)
        conn = await self._get_ssh_conn(node)
        async with conn.start_sftp_client() as sftp:
            async with sftp.open(remote_path, "r") as fh:
                original = str(await fh.read())
            if target_snippet not in original:
                raise ValueError(f"Target snippet not found in '{remote_path}'.")
            updated = original.replace(target_snippet, replacement, 1)
            async with sftp.open(remote_path, "w") as fh:
                await fh.write(updated)
        return f"Updated {remote_path} on {node.id}"
