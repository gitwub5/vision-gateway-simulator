"""Common orchestration helpers for validation experiment scripts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, TypeVar

from common.io import write_json


T = TypeVar("T")


class StageTimer:
    def __init__(self) -> None:
        self.stage_seconds: dict[str, float] = {}

    def run(self, stage_name: str, func: Callable[[], T]) -> T:
        started = perf_counter()
        result = func()
        self.stage_seconds[stage_name] = perf_counter() - started
        return result


def make_prefixed_run_id(started_at: datetime, experiment_name: str, prefix: str) -> str:
    safe_name = experiment_name.replace("/", "_").replace(" ", "_")
    if not safe_name.startswith(f"{prefix}_"):
        safe_name = f"{prefix}_{safe_name}"
    return f"{started_at.strftime('%Y%m%d_%H%M%S')}_{safe_name}"


def resolve_experiment_name(explicit_name: str | None, fallback_name: str | None, default_name: str) -> str:
    if explicit_name:
        return explicit_name
    if fallback_name:
        return fallback_name
    return default_name


def write_manifest(manifest: dict[str, Any], output_path: str | Path) -> None:
    write_json(manifest, output_path)
