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


_QWEN_COMPAT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


@dataclass(frozen=True)
class MemoryRoleConfig:
    """OpenAI-compatible endpoint config for one Mnemosyne role."""

    base_url: str
    api_key: str | None
    model: str


@dataclass(frozen=True)
class MnemosyneConfig:
    """Multi-role cloud API routing config for Mnemosyne (LLM / Embedding / Vision)."""

    llm: MemoryRoleConfig
    embedding: MemoryRoleConfig
    vision: MemoryRoleConfig
    embedding_dim: int = 1024


@dataclass(frozen=True)
class BackupConfig:
    """Cross-platform mount directory backup configuration (no hardcoded target path)."""

    target_dir: Path | None = None
    source_dirs: tuple[Path, ...] = ()
    cron: str = "0 3 * * *"
    retention_days: int = 7


@dataclass(frozen=True)
class MetisConfig:
    """Resolved cross-platform configuration for the Metis backend."""

    home_dir: Path
    workspace_dir: Path
    graph_dir: Path
    skills_dir: Path
    skills_repo_dir: Path = Path(".")
    config_file: Path = Path(".")
    models_file: Path = Path(".")
    static_dir: Path | None = None
    host: str = "127.0.0.1"
    port: int = 9119
    codex_bin: str | None = None
    telegram_enabled: bool = False
    cron_enabled: bool = False
    backup: BackupConfig = field(default_factory=BackupConfig)
    memory: MnemosyneConfig = field(
        default_factory=lambda: MnemosyneConfig(
            llm=MemoryRoleConfig(_QWEN_COMPAT_BASE_URL, None, "qwen-plus"),
            embedding=MemoryRoleConfig(_QWEN_COMPAT_BASE_URL, None, "text-embedding-v3"),
            vision=MemoryRoleConfig(_QWEN_COMPAT_BASE_URL, None, "qwen-vl-plus"),
        )
    )
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

        mem_raw = raw.get("memory") if isinstance(raw.get("memory"), dict) else {}
        shared_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("OPENAI_API_KEY")

        def _role(role: str, env_prefix: str, default_model: str) -> MemoryRoleConfig:
            role_raw = mem_raw.get(role) if isinstance(mem_raw.get(role), dict) else {}
            base_url = str(
                os.environ.get(f"{env_prefix}_BASE_URL")
                or role_raw.get("base_url")
                or _QWEN_COMPAT_BASE_URL
            )
            api_key = (
                os.environ.get(f"{env_prefix}_API_KEY")
                or role_raw.get("api_key")
                or shared_key
            )
            model = str(
                os.environ.get(f"{env_prefix}_MODEL")
                or role_raw.get("model")
                or default_model
            )
            return MemoryRoleConfig(base_url=base_url, api_key=api_key, model=model)

        memory_cfg = MnemosyneConfig(
            llm=_role("llm", "METIS_MEMORY_LLM", "qwen-plus"),
            embedding=_role("embedding", "METIS_MEMORY_EMBEDDING", "text-embedding-v3"),
            vision=_role("vision", "METIS_MEMORY_VISION", "qwen-vl-plus"),
            embedding_dim=int(
                os.environ.get("METIS_MEMORY_EMBEDDING_DIM")
                or mem_raw.get("embedding_dim")
                or 1024
            ),
        )

        workspace_dir = _path("METIS_WORKSPACE", "workspace_dir", home / "workspace")
        graph_dir = _path("METIS_GRAPH_DIR", "graph_dir", home / "memory" / "graph")
        skills_dir = _path("METIS_SKILLS_DIR", "skills_dir", home / "skills")
        skills_repo_dir = _path("METIS_SKILLS_REPO_DIR", "skills_repo_dir", skills_dir)
        models_file = _path("METIS_MODELS_FILE", "models_file", home / "models.json")

        backup_raw = raw.get("backup") if isinstance(raw.get("backup"), dict) else {}
        backup_target_val = os.environ.get("METIS_BACKUP_TARGET_DIR") or backup_raw.get("target_dir")
        backup_target = (
            Path(backup_target_val).expanduser().resolve() if backup_target_val else None
        )
        raw_sources = backup_raw.get("source_dirs")
        if isinstance(raw_sources, list) and raw_sources:
            source_dirs = tuple(Path(str(p)).expanduser().resolve() for p in raw_sources)
        else:
            source_dirs = (workspace_dir, graph_dir)
        backup_cfg = BackupConfig(
            target_dir=backup_target,
            source_dirs=source_dirs,
            cron=str(os.environ.get("METIS_BACKUP_CRON") or backup_raw.get("cron") or "0 3 * * *"),
            retention_days=int(
                os.environ.get("METIS_BACKUP_RETENTION_DAYS")
                or backup_raw.get("retention_days")
                or 7
            ),
        )

        return cls(
            home_dir=home,
            workspace_dir=workspace_dir,
            graph_dir=graph_dir,
            skills_dir=skills_dir,
            skills_repo_dir=skills_repo_dir,
            config_file=cfg_file.expanduser().resolve(),
            models_file=models_file,
            static_dir=_opt_path("METIS_STATIC_DIR", "static_dir"),
            host=str(os.environ.get("METIS_HOST") or raw.get("host") or "127.0.0.1"),
            port=int(os.environ.get("METIS_PORT") or raw.get("port") or 9119),
            codex_bin=str(codex_override) if codex_override else shutil.which("codex"),
            telegram_enabled=_bool("METIS_TELEGRAM_ENABLED", "telegram_enabled", False),
            cron_enabled=_bool("METIS_CRON_ENABLED", "cron_enabled", False),
            backup=backup_cfg,
            memory=memory_cfg,
            extra=raw,
        )

    def ensure_directories(self) -> None:
        """Create required runtime directories if they do not exist."""
        for directory in (self.home_dir, self.workspace_dir, self.graph_dir, self.skills_dir):
            directory.mkdir(parents=True, exist_ok=True)
