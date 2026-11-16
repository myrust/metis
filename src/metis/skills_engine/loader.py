"""Progressive SKILL.md loader (Hermes-inspired): index-only in prompt, full read on demand."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SkillSummary:
    """Lightweight skill metadata injected into the system prompt."""

    name: str
    description: str
    path: Path


def _parse_frontmatter(markdown_text: str) -> tuple[dict[str, str], str]:
    """Extract YAML frontmatter and body from a SKILL.md file."""
    stripped = markdown_text.lstrip()
    if not stripped.startswith("---"):
        return {}, markdown_text
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return {}, markdown_text
    raw_yaml, body = parts[1], parts[2].lstrip("\r\n")
    try:
        parsed = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        return {}, markdown_text
    if not isinstance(parsed, dict):
        return {}, markdown_text
    return {str(k): str(v) for k, v in parsed.items() if v is not None}, body


class SkillRegistry:
    """Discovers SKILL.md files and provides progressive disclosure."""

    def __init__(self, search_dirs: Iterable[Path]) -> None:
        self._search_dirs = [Path(d).expanduser().resolve() for d in search_dirs]
        self._skills: dict[str, SkillSummary] = {}
        self.refresh()

    def refresh(self) -> None:
        """Scan search directories for */SKILL.md files."""
        discovered: dict[str, SkillSummary] = {}
        for base in self._search_dirs:
            if not base.is_dir():
                continue
            for skill_file in sorted(base.glob("*/SKILL.md")):
                meta, _ = _parse_frontmatter(skill_file.read_text(encoding="utf-8"))
                name = meta.get("name") or skill_file.parent.name
                description = meta.get("description") or "No description provided."
                discovered[name] = SkillSummary(
                    name=name,
                    description=description,
                    path=skill_file.resolve(),
                )
        self._skills = discovered

    def list_summaries(self) -> list[SkillSummary]:
        """Return all discovered skill summaries (name + short description only)."""
        return list(self._skills.values())

    def render_prompt_index(self) -> str:
        """Render compact skill index for system prompt injection without full bodies."""
        if not self._skills:
            return ""
        lines = ["Available Skills (load full SKILL.md on demand when relevant):"]
        for skill in self._skills.values():
            lines.append(f"- {skill.name}: {skill.description}")
        return "\n".join(lines)

    def load_skill(self, name: str) -> str:
        """Load the full SKILL.md contents on demand."""
        summary = self._skills.get(name)
        if summary is None:
            raise KeyError(f"Unknown skill: {name}")
        return summary.path.read_text(encoding="utf-8")
