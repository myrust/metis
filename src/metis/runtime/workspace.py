"""Workspace-isolated file operations with line-numbered read and local diff replacement."""

from __future__ import annotations

from pathlib import Path


class WorkspaceViolationError(PermissionError):
    """Raised when a path escapes the configured workspace directory."""


class WorkspaceGuard:
    """Confines file reads/writes/edits to a single root workspace directory."""

    def __init__(self, workspace_dir: Path) -> None:
        self.root = workspace_dir.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, relative_or_abs: str | Path) -> Path:
        """Resolve a path and verify it stays within self.root."""
        candidate = Path(relative_or_abs).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceViolationError(
                f"Path '{relative_or_abs}' escapes workspace '{self.root}'."
            ) from exc
        return resolved

    def read_lines(
        self,
        path: str | Path,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> str:
        """Read 1-indexed line range from a workspace file with line numbers."""
        target = self.resolve_path(path)
        lines = target.read_text(encoding="utf-8").splitlines()
        total = len(lines)
        start = max(1, start_line)
        end = min(total, end_line) if end_line is not None else total
        if start > end and total > 0:
            return ""
        numbered = [f"{idx}: {lines[idx - 1]}" for idx in range(start, end + 1)]
        return "\n".join(numbered)

    def write_file(self, path: str | Path, content: str) -> Path:
        """Write full content to a file inside the workspace."""
        target = self.resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def apply_diff(self, path: str | Path, target_snippet: str, replacement: str) -> Path:
        """Replace an exact local snippet inside a workspace file."""
        target = self.resolve_path(path)
        original = target.read_text(encoding="utf-8")
        if target_snippet not in original:
            raise ValueError(f"Target snippet not found in '{target.name}'.")
        updated = original.replace(target_snippet, replacement, 1)
        target.write_text(updated, encoding="utf-8")
        return target
