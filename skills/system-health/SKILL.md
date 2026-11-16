---
name: system-health
description: Cross-platform macOS and Linux system health inspection (CPU, memory, disk) using psutil.
---

# System Health Check (Cross-Platform)

Collect host CPU, memory, and disk utilization on macOS and Linux without OS-specific shell commands.

## Procedure

Run the following Python snippet using `psutil`:

```python
import json
import platform
import psutil
from pathlib import Path

home = Path.home()
disk = psutil.disk_usage(str(home))
mem = psutil.virtual_memory()

report = {
    "platform": platform.system(),
    "cpu_percent": psutil.cpu_percent(interval=0.5),
    "cpu_count": psutil.cpu_count(logical=True),
    "memory_percent": mem.percent,
    "memory_available_gb": round(mem.available / (1024 ** 3), 2),
    "disk_percent": disk.percent,
    "disk_free_gb": round(disk.free / (1024 ** 3), 2),
}
print(json.dumps(report, indent=2))
```

## Thresholds
- Warn if `cpu_percent >= 90`, `memory_percent >= 85`, or `disk_percent >= 90`.
