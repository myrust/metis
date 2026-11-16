---
name: workspace-backup
description: Cross-platform mount directory backup of Metis workspace and graph directories with exclusion and retention pruning.
---

# Workspace & Graph Backup

Archive `backup.source_dirs` (excluding `_refs`, `.venv`, `__pycache__`) to `/tmp`, move to `METIS_BACKUP_TARGET_DIR` (or `config.json` `backup.target_dir`), and prune backups older than `retention_days`.

If `backup.target_dir` is `null` / unset, backup is skipped automatically.

## Procedure

1. Trigger via API: `POST /api/backup/run`
2. Or run via Python:

```python
from metis.config import MetisConfig
from metis.automation.backup import BackupService

cfg = MetisConfig.load()
result = BackupService(cfg.backup).run_backup()
print(result)
```

## Verification
- Confirm `status` is `"completed"` (or `"skipped"` when `target_dir` is `null`).
- Confirm the `.tar.gz` archive exists in `target_dir` and excludes `_refs`, `.venv`, and `__pycache__`.
