"""Cross-platform host system metrics collector (CPU, Memory, Disk, Disk IO, Processes)."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

import psutil


def collect_system_metrics(top_n: int = 8) -> dict[str, Any]:
    """Collect CPU, memory, disk, disk IO, and top processes using psutil."""
    cpu_pct = round(psutil.cpu_percent(interval=0.1), 1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(str(Path.home()))
    try:
        io = psutil.disk_io_counters()
    except (RuntimeError, OSError):
        io = None

    processes: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            processes.append(
                {
                    "pid": int(info.get("pid") or 0),
                    "name": str(info.get("name") or "unknown"),
                    "cpu_percent": round(float(info.get("cpu_percent") or 0.0), 1),
                    "memory_percent": round(float(info.get("memory_percent") or 0.0), 2),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    processes.sort(key=lambda p: (p["memory_percent"], p["cpu_percent"]), reverse=True)

    return {
        "platform": platform.system(),
        "cpu_percent": cpu_pct,
        "cpu_count": psutil.cpu_count(logical=True) or 1,
        "memory_percent": round(float(mem.percent), 1),
        "memory_used_gb": round(mem.used / (1024**3), 2),
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "disk_percent": round(float(disk.percent), 1),
        "disk_used_gb": round(disk.used / (1024**3), 2),
        "disk_total_gb": round(disk.total / (1024**3), 2),
        "disk_io": {
            "read_mb": round(io.read_bytes / (1024**2), 2) if io else 0.0,
            "write_mb": round(io.write_bytes / (1024**2), 2) if io else 0.0,
            "read_count": int(io.read_count) if io else 0,
            "write_count": int(io.write_count) if io else 0,
        },
        "process_count": len(psutil.pids()),
        "top_processes": processes[:top_n],
    }
