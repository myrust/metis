"""Cross-platform mount directory backup service (no hardcoded target path)."""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from metis.config import BackupConfig

_EXCLUDED_DIR_NAMES = {"_refs", ".venv", "__pycache__"}


def _tar_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
    parts = Path(tarinfo.name).parts
    if any(part in _EXCLUDED_DIR_NAMES for part in parts):
        return None
    return tarinfo


class BackupService:
    """Archives configured source_dirs to /tmp, moves to target_dir, and prunes expired backups."""

    def __init__(self, config: BackupConfig) -> None:
        self.config = config

    def run_backup(self, now_ts: float | None = None) -> dict[str, Any]:
        """Execute one backup run; skips cleanly when target_dir is null."""
        target = self.config.target_dir
        if target is None:
            return {"status": "skipped", "reason": "backup.target_dir is not configured"}

        if not target.is_dir():
            raise FileNotFoundError(f"Backup target_dir does not exist or is not a directory: {target}")
        if not os.access(target, os.W_OK):
            raise PermissionError(f"Backup target_dir is not writable: {target}")

        ts_str = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archive_name = f"metis-backup-{ts_str}.tar.gz"
        tmp_path = Path(tempfile.gettempdir()) / archive_name

        with tarfile.open(tmp_path, "w:gz") as tar:
            for src in self.config.source_dirs:
                if src.exists():
                    tar.add(src, arcname=src.name, filter=_tar_filter)

        dest_path = target / archive_name
        shutil.move(str(tmp_path), str(dest_path))

        removed: list[str] = []
        if self.config.retention_days > 0:
            cutoff = (now_ts if now_ts is not None else time.time()) - (
                self.config.retention_days * 86400
            )
            for item in sorted(target.glob("metis-backup-*.tar.gz")):
                if item != dest_path and item.is_file() and item.stat().st_mtime < cutoff:
                    item.unlink()
                    removed.append(item.name)

        return {
            "status": "completed",
            "archive": str(dest_path),
            "pruned": removed,
        }
