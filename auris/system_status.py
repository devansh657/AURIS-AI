from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import threading
import ctypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_CPU_SAMPLE_LOCK = threading.Lock()
_PREVIOUS_CPU_SAMPLE: tuple[int, int] | None = None


def collect_system_status() -> dict[str, Any]:
    cwd = Path.cwd()
    disk = shutil.disk_usage(cwd.anchor or cwd)
    memory = _memory_status()
    cpu = {
        "model": _cpu_model(),
        "utilization_percent": _cpu_utilization_percent(),
    }
    status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "machine": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cwd": str(cwd),
        "cpu_count": os.cpu_count(),
        "cpu": cpu,
        "memory": memory,
        "gpu": _gpu_status(),
        "uptime_seconds": _uptime_seconds(),
        "power": _power_status(),
        "network": _network_status(),
        "disk": {
            "total_gb": _gb(disk.total),
            "used_gb": _gb(disk.used),
            "free_gb": _gb(disk.free),
        },
        "top_processes": _top_process_names(),
    }
    return status


def _cpu_model() -> str:
    model = platform.processor().strip()
    if platform.system().lower() != "windows":
        return model
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        ) as key:
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
    except (OSError, ImportError):
        return model


def _cpu_utilization_percent() -> float | None:
    if platform.system().lower() != "windows":
        return None

    class FileTime(ctypes.Structure):
        _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]

    idle = FileTime()
    kernel = FileTime()
    user = FileTime()
    if not ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
    ):
        return None

    def value(item: FileTime) -> int:
        return (int(item.high) << 32) | int(item.low)

    global _PREVIOUS_CPU_SAMPLE
    current_idle = value(idle)
    current_total = value(kernel) + value(user)
    with _CPU_SAMPLE_LOCK:
        previous = _PREVIOUS_CPU_SAMPLE
        _PREVIOUS_CPU_SAMPLE = (current_idle, current_total)
    if previous is None:
        return None
    idle_delta = current_idle - previous[0]
    total_delta = current_total - previous[1]
    if total_delta <= 0:
        return None
    return round(max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0)), 1)


def _memory_status() -> dict[str, float] | None:
    if platform.system().lower() != "windows":
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    memory = MemoryStatus()
    memory.length = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        return None
    used = memory.total_physical - memory.available_physical
    return {
        "total_gb": _gb(memory.total_physical),
        "used_gb": _gb(used),
        "available_gb": _gb(memory.available_physical),
        "utilization_percent": float(memory.memory_load),
    }


def _gpu_status() -> dict[str, Any] | None:
    if platform.system().lower() != "windows":
        return None
    fields = (
        "name,utilization.gpu,memory.used,memory.total,temperature.gpu,"
        "power.draw,clocks.gr"
    )
    try:
        result = subprocess.run(
            ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    values = [item.strip() for item in result.stdout.splitlines()[0].split(",")]
    if len(values) != 7:
        return None
    return {
        "name": values[0],
        "utilization_percent": _number(values[1]),
        "memory_used_mb": _number(values[2]),
        "memory_total_mb": _number(values[3]),
        "temperature_c": _number(values[4]),
        "power_watts": _number(values[5]),
        "clock_mhz": _number(values[6]),
    }


def _uptime_seconds() -> int | None:
    if platform.system().lower() != "windows":
        return None
    return int(ctypes.windll.kernel32.GetTickCount64() // 1000)


def _power_status() -> dict[str, Any] | None:
    if platform.system().lower() != "windows":
        return None

    class SystemPowerStatus(ctypes.Structure):
        _fields_ = [
            ("ac_line_status", ctypes.c_ubyte),
            ("battery_flag", ctypes.c_ubyte),
            ("battery_life_percent", ctypes.c_ubyte),
            ("system_status_flag", ctypes.c_ubyte),
            ("battery_life_time", ctypes.c_ulong),
            ("battery_full_life_time", ctypes.c_ulong),
        ]

    power = SystemPowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)):
        return None
    return {
        "ac_line": True if power.ac_line_status == 1 else False if power.ac_line_status == 0 else None,
        "battery_percent": None if power.battery_life_percent == 255 else int(power.battery_life_percent),
    }


def _network_status() -> dict[str, Any]:
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except OSError:
        local_ip = None
    return {"local_ip": local_ip, "connectivity": "local_interface" if local_ip else "unavailable"}


def _number(value: str) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _gb(value: int) -> float:
    return round(value / (1024**3), 2)


def _top_process_names() -> list[str]:
    if platform.system().lower() != "windows":
        return []

    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    names: list[str] = []
    for line in result.stdout.splitlines()[:12]:
        if not line.strip():
            continue
        names.append(line.split(",", 1)[0].strip('"'))
    return names
