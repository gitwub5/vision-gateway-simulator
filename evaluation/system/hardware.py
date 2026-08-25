"""Hardware/backend snapshot helpers for experiment manifests."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from typing import Any


def collect_hardware_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": sys.version.split()[0],
        "torch": _torch_snapshot(),
        "nvidia_smi": _nvidia_smi_snapshot(),
        "notes": [
            "This snapshot records available compute backends. Per-run GPU utilization requires platform-specific sampling such as nvidia-smi dmon on NVIDIA GPUs or tegrastats on Jetson.",
        ],
    }
    return snapshot


def _torch_snapshot() -> dict[str, Any]:
    try:
        import torch
    except Exception as exc:
        return {
            "available": False,
            "error": repr(exc),
        }

    cuda_available = bool(torch.cuda.is_available())
    mps_backend = getattr(torch.backends, "mps", None)
    mps_available = bool(mps_backend is not None and mps_backend.is_available())
    mps_built = bool(mps_backend is not None and mps_backend.is_built())

    devices = []
    if cuda_available:
        for index in range(torch.cuda.device_count()):
            properties = torch.cuda.get_device_properties(index)
            devices.append(
                {
                    "index": index,
                    "name": torch.cuda.get_device_name(index),
                    "total_memory_bytes": int(properties.total_memory),
                    "major": int(properties.major),
                    "minor": int(properties.minor),
                }
            )

    return {
        "available": True,
        "version": getattr(torch, "__version__", ""),
        "cuda_available": cuda_available,
        "cuda_device_count": int(torch.cuda.device_count()) if cuda_available else 0,
        "cuda_devices": devices,
        "mps_available": mps_available,
        "mps_built": mps_built,
    }


def _nvidia_smi_snapshot() -> dict[str, Any]:
    if shutil.which("nvidia-smi") is None:
        return {
            "available": False,
        }

    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=5)
    except Exception as exc:
        return {
            "available": True,
            "error": repr(exc),
        }

    devices = []
    for index, line in enumerate(result.stdout.splitlines()):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 3:
            devices.append(
                {
                    "index": index,
                    "name": parts[0],
                    "memory_total_mb": _safe_int(parts[1]),
                    "driver_version": parts[2],
                }
            )

    return {
        "available": True,
        "devices": devices,
    }


def _safe_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None
