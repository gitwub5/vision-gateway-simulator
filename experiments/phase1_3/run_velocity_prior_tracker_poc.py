"""Run Phase 1.3 traffic velocity/scale-aware tracker prior POC."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common import GroundTruthAnnotation
from common.io import load_yaml_config, write_json, write_jsonl
from data_loader.annotation_loader import create_annotation_loader
from data_loader.dataset_stream import create_dataset_stream, load_dataset_config
from evaluation.metrics.class_filter import filter_gt_by_target_classes
from evaluation.reports.velocity_prior_tracker import (
    VelocityTrackerFrame,
    build_velocity_tracker_report,
    default_velocity_tracker_profiles,
    write_velocity_tracker_report_json,
    write_velocity_tracker_report_markdown,
)

DEFAULT_OUTPUT_ROOT = "outputs/velocity_prior_tracker_poc"


def run_velocity_prior_tracker_poc(
    dataset_config_path: str | Path,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    experiment_name: str | None = None,
    run_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    dataset_path = resolve_project_path(dataset_config_path)
    raw_config = load_yaml_config(dataset_path)
    dataset_config = load_dataset_config(dataset_path)
    if limit is not None:
        dataset_config = replace(dataset_config, frame_limit=limit)

    frames = _load_frame_metadata(dataset_config)
    annotations = _load_target_annotations(raw_config, dataset_config)
    target_classes = _target_classes_from_config(raw_config)
    name = experiment_name or str(raw_config.get("name") or dataset_path.stem)
    suffix = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    selected_run_id = run_id or f"{name}_velocity_prior_tracker_{suffix}"
    run_root = Path(output_root) / selected_run_id
    report_root = run_root / "reports"
    frame_records_path = run_root / "velocity_prior_tracker_frames.jsonl"
    report_json_path = report_root / "velocity_prior_tracker_report.json"
    report_md_path = report_root / "velocity_prior_tracker_report.md"

    report, frame_records = build_velocity_tracker_report(
        frames=frames,
        ground_truth=annotations,
        profiles=default_velocity_tracker_profiles(),
        dataset_config=project_relative(dataset_path),
        experiment_name=name,
        target_classes=target_classes,
    )
    write_jsonl(frame_records, frame_records_path)
    write_velocity_tracker_report_json(report, report_json_path)
    write_velocity_tracker_report_markdown(report, report_md_path)
    manifest = {
        "schema_version": 1,
        "pipeline_type": "velocity_prior_tracker_poc",
        "experiment_name": name,
        "run_id": selected_run_id,
        "dataset_config": project_relative(dataset_path),
        "limit": limit,
        "target_classes": list(target_classes),
        "outputs": {
            "frame_records": str(frame_records_path),
            "report_json": str(report_json_path),
            "report_markdown": str(report_md_path),
        },
        "summary": {
            "frame_count": report.frame_count,
            "target_frame_count": report.target_frame_count,
            "target_gt_count": report.target_gt_count,
            "profiles": {
                name: {
                    "full_frame_detector_call_reduction": profile.full_frame_detector_call_reduction,
                    "effective_input_area_reduction": profile.effective_input_area_reduction,
                    "target_gt_recall": profile.target_gt_recall,
                    "memory_frame_target_gt_recall": profile.memory_frame_target_gt_recall,
                    "average_roi_count_per_memory_frame": profile.average_roi_count_per_memory_frame,
                    "max_consecutive_memory_miss_frames": profile.max_consecutive_memory_miss_frames,
                }
                for name, profile in report.profiles.items()
            },
        },
    }
    write_json(manifest, run_root / "manifest.json")
    return {"run_root": str(run_root), **manifest}


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def project_relative(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return str(candidate.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(candidate)


def _load_frame_metadata(dataset_config) -> list[VelocityTrackerFrame]:
    frames: list[VelocityTrackerFrame] = []
    for frame_index, packet in enumerate(create_dataset_stream(dataset_config)):
        frames.append(
            VelocityTrackerFrame(
                camera_id=packet.camera_id,
                frame_id=packet.frame_id,
                frame_index=frame_index,
                timestamp=packet.timestamp,
                frame_size=packet.original_size,
            )
        )
    if not frames:
        raise ValueError("Dataset stream produced no frames.")
    return frames


def _load_target_annotations(raw_config: dict[str, Any], dataset_config) -> list[GroundTruthAnnotation]:
    loader = create_annotation_loader(raw_config.get("annotations"), dataset_config)
    if loader is None:
        return []
    annotations = loader.load()
    return filter_gt_by_target_classes(annotations, _target_classes_from_config(raw_config))


def _target_classes_from_config(raw_config: dict[str, Any]) -> tuple[str, ...]:
    return tuple(raw_config.get("validation", {}).get("target_classes") or ())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1.3 traffic velocity prior tracker POC.")
    parser.add_argument("--dataset-config", required=True)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--experiment-name")
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run_velocity_prior_tracker_poc(
        dataset_config_path=args.dataset_config,
        output_root=args.output_root,
        experiment_name=args.experiment_name,
        run_id=args.run_id,
        limit=args.limit,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
