"""Cross-platform configuration loader for Metis.

All paths (home, workspace, graph storage, CLI binaries) and service settings
are resolved from environment variables or ~/.metis/config.json, falling back to
~/.metis/ and shutil.which() dynamic discovery with zero OS-specific hardcoding.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def default_metis_home() -> Path:
    """Return the Metis home directory (METIS_HOME or ~/.metis/)."""
    env_home = os.environ.get("METIS_HOME")
    return Path(env_home).expanduser().resolve() if env_home else (Path.home() / ".metis").resolve()


def _load_json_config(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


@dataclass(frozen=True)
class MetisConfig:
    """Resolved cross-platform configuration for the Metis backend."""

    home_dir: Path
    workspace_dir: Path
    graph_dir: Path
    skills_dir: Path
    static_dir: Path | None = None
    host: str = "127.0.0.1"
    port: int = 9119
    codex_bin: str | None = None
    telegram_enabled: bool = False
    cron_enabled: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Path | None = None) -> MetisConfig:
        """Load configuration from env vars -> config file -> cross-platform defaults."""
        home = default_metis_home()
        cfg_file = config_path or Path(os.environ.get("METIS_CONFIG", home / "config.json"))
        raw = _load_json_config(cfg_file)

        def _path(env_key: str, cfg_key: str, fallback: Path) -> Path:
            val = os.environ.get(env_key) or raw.get(cfg_key)
            return Path(val).expanduser().resolve() if val else fallback.resolve()

        def _opt_path(env_key: str, cfg_key: str) -> Path | None:
            val = os.environ.get(env_key) or raw.get(cfg_key)
            return Path(val).expanduser().resolve() if val else None

        def _bool(env_key: str, cfg_key: str, default: bool = False) -> bool:
            if env_key in os.environ:
                return os.environ[env_key].strip().lower() in {"1", "true", "yes", "on"}
            if cfg_key in raw:
                return bool(raw[cfg_key])
            return default

        codex_override = os.environ.get("METIS_CODEX_BIN") or raw.get("codex_bin")

        return cls(
            home_dir=home,
            workspace_dir=_path("METIS_WORKSPACE", "workspace_dir", home / "workspace"),
            graph_dir=_path("METIS_GRAPH_DIR", "graph_dir", home / "memory" / "graph"),
            skills_dir=_path("METIS_SKILLS_DIR", "skills_dir", home / "skills"),
            static_dir=_opt_path("METIS_STATIC_DIR", "static_dir"),
            host=str(os.environ.get("METIS_HOST") or raw.get("host") or "127.0.0.1"),
            port=int(os.environ.get("METIS_PORT") or raw.get("port") or 9119),
            codex_bin=str(codex_override) if codex_override else shutil.which("codex"),
            telegram_enabled=_bool("METIS_TELEGRAM_ENABLED", "telegram_enabled", False),
            cron_enabled=_bool("METIS_CRON_ENABLED", "cron_enabled", False),
            extra=raw,
        )

    def ensure_directories(self) -> None:
        """Create required runtime directories if they do not exist."""
        for directory in (self.home_dir, self.workspace_dir, self.graph_dir, self.skills_dir):
            directory.mkdir(parents=True, exist_ok=True)
