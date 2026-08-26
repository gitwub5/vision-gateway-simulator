"""Common orchestration helpers for validation experiment scripts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import hashlib
from pathlib import Path
import subprocess
from time import perf_counter
from typing import Any, TypeVar

from common.io import read_json, write_json


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


def read_manifest(input_path: str | Path, expected_pipeline_type: str | None = None) -> dict[str, Any]:
    manifest = read_json(input_path)
    if manifest.get("schema_version") != 1:
        raise ValueError(f"Unsupported manifest schema_version: {manifest.get('schema_version')}")
    if expected_pipeline_type is not None and manifest.get("pipeline_type") != expected_pipeline_type:
        raise ValueError(
            f"Expected pipeline_type {expected_pipeline_type}, got {manifest.get('pipeline_type')}"
        )
    return manifest


def file_provenance(path: str | Path) -> dict[str, str]:
    resolved = Path(path).resolve()
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return {
        "path": str(path),
        "resolved_path": str(resolved),
        "sha256": digest,
    }


def optional_file_provenance(path: str | Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    candidate = Path(path)
    return file_provenance(candidate) if candidate.is_file() else None


def collect_git_provenance(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root)
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return {"revision": None, "dirty": None}
    return {
        "revision": revision,
        "dirty": bool(status.strip()),
    }
