"""Manifest-based loaders for saved ROI proposal runs."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common.io import read_jsonl
from experiments.runner_common import read_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FrameKey = tuple[str, int]


@dataclass(frozen=True)
class RoiRunArtifacts:
    label: str
    root: Path
    manifest: dict[str, Any]
    rois_by_frame: dict[FrameKey, list[dict[str, Any]]]
    frames_by_frame: dict[FrameKey, dict[str, Any]]
    tiles_by_frame: dict[FrameKey, list[dict[str, Any]]]
    ground_truth_by_frame: dict[FrameKey, list[dict[str, Any]]]
    feedback_by_frame: dict[FrameKey, list[dict[str, Any]]]
    tile_trace_available: bool

    @property
    def run_id(self) -> str:
        return str(self.manifest.get("run_id", self.root.name))

    @property
    def dataset_config_path(self) -> Path:
        raw_path = self.manifest.get("inputs", {}).get("dataset_config")
        if not raw_path:
            raise ValueError(f"Run {self.run_id} does not record dataset_config.")
        return resolve_project_path(raw_path)

    @property
    def compatibility_key(self) -> dict[str, Any]:
        resolved = self.manifest.get("provenance", {}).get("resolved", {})
        dataset = resolved.get("dataset")
        target_classes = resolved.get("target_classes")
        if not isinstance(dataset, dict) or target_classes is None:
            raise ValueError(f"Run {self.run_id} lacks resolved dataset provenance.")
        return {
            "input_path": dataset.get("input_path"),
            "camera_id": dataset.get("camera_id"),
            "start_frame": dataset.get("start_frame"),
            "effective_frame_limit": dataset.get("effective_frame_limit"),
            "target_classes": list(target_classes),
        }


def load_roi_run(run_root: str | Path, label: str | None = None) -> RoiRunArtifacts:
    root = Path(run_root)
    manifest = read_manifest(root / "manifest.json", expected_pipeline_type="roi_proposal_validation")
    outputs = manifest.get("outputs", {})

    roi_path = artifact_path(root, outputs, "roi_metadata", "roi_metadata/rule_roi.jsonl")
    frame_path = artifact_path(root, outputs, "frame_metadata", "roi_metadata/gate_decisions.jsonl")
    tile_path = artifact_path(root, outputs, "tile_metadata", "roi_metadata/tile_metadata.jsonl")
    gt_path = artifact_path(root, outputs, "ground_truth", "annotations/ground_truth.jsonl")
    feedback_path = artifact_path(
        root,
        outputs,
        "reference_feedback_detections",
        "detections/reference_feedback_full_frame.jsonl",
    )
    return RoiRunArtifacts(
        label=label or str(manifest.get("experiment_name", root.name)),
        root=root,
        manifest=manifest,
        rois_by_frame=group_raw_records(roi_path) if roi_path.is_file() else {},
        frames_by_frame=index_raw_records(frame_path) if frame_path.is_file() else {},
        tiles_by_frame=group_raw_records(tile_path) if tile_path.is_file() else {},
        ground_truth_by_frame=group_raw_records(gt_path) if gt_path.is_file() else {},
        feedback_by_frame=group_raw_records(feedback_path) if feedback_path.is_file() else {},
        tile_trace_available=tile_path.is_file(),
    )


def load_run_spec(spec: str) -> RoiRunArtifacts:
    if "=" not in spec:
        raise ValueError(f"Run spec must be label=path: {spec}")
    label, raw_root = spec.split("=", 1)
    return load_roi_run(raw_root, label=label)


def ensure_compatible_runs(runs: list[RoiRunArtifacts]) -> dict[str, Any]:
    if not runs:
        raise ValueError("At least one ROI run is required.")
    expected = runs[0].compatibility_key
    for run in runs[1:]:
        if run.compatibility_key != expected:
            raise ValueError(
                f"Run {run.label} is incompatible with {runs[0].label}: "
                f"expected {expected}, got {run.compatibility_key}"
            )
    return expected


def artifact_path(
    run_root: Path,
    outputs: dict[str, Any],
    key: str,
    fallback_relative: str,
) -> Path:
    raw_path = outputs.get(key)
    if raw_path:
        candidate = Path(str(raw_path))
        if candidate.is_absolute():
            return candidate
        project_candidate = PROJECT_ROOT / candidate
        if project_candidate.exists():
            return project_candidate
    return run_root / fallback_relative


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def group_raw_records(path: str | Path) -> dict[FrameKey, list[dict[str, Any]]]:
    grouped: dict[FrameKey, list[dict[str, Any]]] = defaultdict(list)
    for record in read_jsonl(path):
        grouped[record_frame_key(record)].append(record)
    return dict(grouped)


def index_raw_records(path: str | Path) -> dict[FrameKey, dict[str, Any]]:
    return {record_frame_key(record): record for record in read_jsonl(path)}


def record_frame_key(record: dict[str, Any]) -> FrameKey:
    return str(record.get("camera_id", record.get("source_id", ""))), int(record["frame_id"])
