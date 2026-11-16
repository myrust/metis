"""Session skill distiller: extracts reusable SKILL.md files from completed sessions."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from pathlib import Path

from metis.providers.base import BaseModelProvider, ProviderRequest


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-")
    return slug or "distilled-skill"


class SkillDistiller:
    """Distills a session transcript into a structured SKILL.md saved under skills_repo_dir."""

    def __init__(self, skills_dir: Path, provider: BaseModelProvider | None = None) -> None:
        self.skills_dir = Path(skills_dir).expanduser().resolve()
        self.provider = provider

    async def distill_from_messages(
        self,
        skill_name: str,
        description: str,
        transcript: Sequence[str],
        auto_sync_git: bool = False,
    ) -> Path:
        """Create a SKILL.md from session messages and optionally sync via native git CLI."""
        slug = _slugify(skill_name)
        body: str | None = None

        if self.provider is not None and self.provider.is_available():
            prompt = (
                "Distill the following solved session transcript into concise, reusable "
                "Markdown instructions (numbered steps + verification checklist).\n\n"
                + "\n".join(transcript)
            )
            body = await self.provider.generate(
                ProviderRequest(
                    prompt=prompt,
                    system_prompt="You are a technical skill author. Output clean Markdown only.",
                )
            )

        if not body or not body.strip():
            steps = "\n".join(f"{idx}. {line}" for idx, line in enumerate(transcript, start=1))
            body = f"## Procedure\n\n{steps}\n\n## Verification\n\n- Confirm expected output and exit status.\n"

        content = f"---\nname: {slug}\ndescription: {description.strip()}\n---\n\n# {slug}\n\n{body.strip()}\n"
        target_dir = self.skills_dir / slug
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / "SKILL.md"
        target_file.write_text(content, encoding="utf-8")

        if auto_sync_git and (self.skills_dir / ".git").exists():
            await self._git_commit_and_push(target_file, slug)

        return target_file

    async def _git_commit_and_push(self, skill_file: Path, slug: str) -> None:
        """Invoke native git CLI inside skills_repo_dir to commit and push a new SKILL.md."""
        rel = str(skill_file.relative_to(self.skills_dir))
        for cmd in (
            ["git", "add", rel],
            ["git", "commit", "-m", f"feat(skills): distill {slug}"],
            ["git", "push"],
        ):
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.skills_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                break
