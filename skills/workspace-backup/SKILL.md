---
name: workspace-backup
description: Cross-platform incremental archive backup of the Metis workspace and Mnemosyne graph directory.
---

# Workspace & Graph Incremental Backup

Create a compressed `.tar.gz` snapshot of `METIS_WORKSPACE` and `METIS_GRAPH_DIR` when file mtimes/sizes have changed since the last manifest.

## Procedure

```python
import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from metis.config import MetisConfig

cfg = MetisConfig.load()
backup_root = cfg.home_dir / "backups"
backup_root.mkdir(parents=True, exist_ok=True)
manifest_path = backup_root / "manifest.json"

def compute_state(dirs: list[Path]) -> dict[str, list[int | float]]:
    state: dict[str, list[int | float]] = {}
    for base in dirs:
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file():
                st = p.stat()
                state[str(p)] = [st.st_size, round(st.st_mtime, 3)]
    return state

targets = [cfg.workspace_dir, cfg.graph_dir]
current = compute_state(targets)
previous = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}

if current == previous:
    print("No changes detected since last backup.")
else:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = backup_root / f"metis-backup-{ts}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for d in targets:
            if d.exists():
                tar.add(d, arcname=d.name)
    manifest_path.write_text(json.dumps(current, indent=2))
    print(f"Created incremental backup: {archive}")
```

## Verification
- Confirm the `.tar.gz` archive exists and is non-empty.
- Confirm `manifest.json` was updated.
