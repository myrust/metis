"""Session skill distiller: extracts reusable SKILL.md files from completed sessions."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from metis.providers.base import BaseModelProvider, ProviderRequest


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-")
    return slug or "distilled-skill"


class SkillDistiller:
    """Distills a session transcript into a structured SKILL.md saved under skills_dir."""

    def __init__(self, skills_dir: Path, provider: BaseModelProvider | None = None) -> None:
        self.skills_dir = Path(skills_dir).expanduser().resolve()
        self.provider = provider

    async def distill_from_messages(
        self,
        skill_name: str,
        description: str,
        transcript: Sequence[str],
    ) -> Path:
        """Create a SKILL.md from session messages using provider or structured fallback."""
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
        return target_file
