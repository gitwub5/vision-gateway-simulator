"""Run Phase 1.3-B temporal gate POC on one annotated dataset."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
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
from evaluation.reports.temporal_gate import (
    TemporalFrameRecord,
    build_temporal_gate_report,
    default_temporal_gate_profiles,
    write_temporal_gate_report_json,
    write_temporal_gate_report_markdown,
)

DEFAULT_OUTPUT_ROOT = "outputs/temporal_gate_poc"


def run_temporal_gate_poc(
    dataset_config_path: str | Path,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    experiment_name: str | None = None,
    run_id: str | None = None,
    limit: int | None = None,
    analysis_width: int = 160,
) -> dict[str, Any]:
    dataset_path = resolve_project_path(dataset_config_path)
    raw_config = load_yaml_config(dataset_path)
    dataset_config = load_dataset_config(dataset_path)
    if limit is not None:
        dataset_config = replace(dataset_config, frame_limit=limit)

    annotations = _load_target_annotations(raw_config, dataset_config)
    annotations_by_frame = _group_annotations_by_frame(annotations)
    name = experiment_name or str(raw_config.get("name") or dataset_path.stem)
    suffix = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    selected_run_id = run_id or f"{name}_temporal_gate_{suffix}"
    run_root = Path(output_root) / selected_run_id
    report_root = run_root / "reports"
    records_path = run_root / "temporal_gate_frames.jsonl"
    report_json_path = report_root / "temporal_gate_report.json"
    report_md_path = report_root / "temporal_gate_report.md"

    frame_records = _collect_frame_records(
        dataset_config=dataset_config,
        annotations_by_frame=annotations_by_frame,
        analysis_width=analysis_width,
    )
    write_jsonl(frame_records, records_path)
    target_classes = _target_classes_from_config(raw_config)
    report = build_temporal_gate_report(
        records=frame_records,
        profiles=default_temporal_gate_profiles(),
        dataset_config=project_relative(dataset_path),
        experiment_name=name,
        target_classes=target_classes,
    )
    write_temporal_gate_report_json(report, report_json_path)
    write_temporal_gate_report_markdown(report, report_md_path)

    manifest = {
        "schema_version": 1,
        "pipeline_type": "temporal_gate_poc",
        "experiment_name": name,
        "run_id": selected_run_id,
        "dataset_config": project_relative(dataset_path),
        "limit": limit,
        "analysis_width": analysis_width,
        "target_classes": list(target_classes),
        "outputs": {
            "frame_records": str(records_path),
            "report_json": str(report_json_path),
            "report_markdown": str(report_md_path),
        },
        "summary": {
            "frame_count": report.frame_count,
            "target_frame_count": report.target_frame_count,
            "target_gt_count": report.target_gt_count,
            "profiles": {
                name: {
                    "detector_call_reduction": profile.detector_call_reduction,
                    "target_frame_recall": profile.target_frame_recall,
                    "target_gt_recall": profile.target_gt_recall,
                    "skipped_target_frame_count": profile.skipped_target_frame_count,
                    "max_target_skip_run_frames": profile.max_target_skip_run_frames,
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


def _load_target_annotations(raw_config: dict[str, Any], dataset_config) -> list[GroundTruthAnnotation]:
    loader = create_annotation_loader(raw_config.get("annotations"), dataset_config)
    if loader is None:
        return []
    annotations = loader.load()
    target_classes = _target_classes_from_config(raw_config)
    return filter_gt_by_target_classes(annotations, target_classes)


def _target_classes_from_config(raw_config: dict[str, Any]) -> tuple[str, ...]:
    return tuple(raw_config.get("validation", {}).get("target_classes") or ())


def _group_annotations_by_frame(
    annotations: list[GroundTruthAnnotation],
) -> dict[tuple[str, int], list[GroundTruthAnnotation]]:
    grouped: dict[tuple[str, int], list[GroundTruthAnnotation]] = defaultdict(list)
    for annotation in annotations:
        grouped[(annotation.camera_id, annotation.frame_id)].append(annotation)
    return dict(grouped)


def _collect_frame_records(
    dataset_config,
    annotations_by_frame: dict[tuple[str, int], list[GroundTruthAnnotation]],
    analysis_width: int,
) -> list[TemporalFrameRecord]:
    records: list[TemporalFrameRecord] = []
    previous_luma = None
    for frame_index, packet in enumerate(create_dataset_stream(dataset_config)):
        luma = _downsample_luma(packet.frame, analysis_width)
        if previous_luma is None:
            delta_mean = 0.0
            delta_p95 = 0.0
        else:
            diff = _abs_luma_diff(luma, previous_luma)
            delta_mean = float(diff.mean())
            delta_p95 = float(_np_percentile(diff, 95))
        previous_luma = luma

        gt_records = annotations_by_frame.get((packet.camera_id, packet.frame_id), [])
        records.append(
            TemporalFrameRecord(
                camera_id=packet.camera_id,
                frame_id=packet.frame_id,
                timestamp=packet.timestamp,
                frame_index=frame_index,
                has_target=bool(gt_records),
                target_gt_count=len(gt_records),
                scene_delta_mean=delta_mean,
                scene_delta_p95=delta_p95,
            )
        )
    return records


def _downsample_luma(frame, analysis_width: int):
    cv2 = _require_cv2()
    if len(frame.shape) == 2:
        luma = frame
    else:
        luma = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    height, width = luma.shape[:2]
    target_width = max(1, analysis_width)
    target_height = max(1, round(height * target_width / max(width, 1)))
    resized = cv2.resize(luma, (target_width, target_height), interpolation=cv2.INTER_AREA)
    return resized.astype("float32") / 255.0


def _abs_luma_diff(current, previous):
    np = _require_numpy()
    if current.shape != previous.shape:
        raise ValueError(f"Temporal luma shape changed: {previous.shape} -> {current.shape}")
    return np.abs(current - previous)


def _np_percentile(values, percentile: float) -> float:
    np = _require_numpy()
    return float(np.percentile(values, percentile))


def _require_cv2():
    try:
        import cv2
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "OpenCV is required for temporal gate POC. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return cv2


def _require_numpy():
    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "NumPy is required for temporal gate POC. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1.3-B temporal gate POC.")
    parser.add_argument("--dataset-config", required=True)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--experiment-name")
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--analysis-width", type=int, default=160)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run_temporal_gate_poc(
        dataset_config_path=args.dataset_config,
        output_root=args.output_root,
        experiment_name=args.experiment_name,
        run_id=args.run_id,
        limit=args.limit,
        analysis_width=args.analysis_width,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
