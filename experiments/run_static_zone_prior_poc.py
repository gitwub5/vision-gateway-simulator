"""Run Phase 1.3-C static zone / camera-prior POC on one annotated dataset."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common import FrameSize, GroundTruthAnnotation
from common.io import load_yaml_config, write_json, write_jsonl
from data_loader.annotation_loader import create_annotation_loader
from data_loader.dataset_stream import create_dataset_stream, load_dataset_config
from evaluation.metrics.class_filter import filter_gt_by_target_classes
from evaluation.reports.static_zone_prior import (
    GridShape,
    build_static_zone_prior_report,
    default_static_zone_profiles,
    write_static_zone_prior_report_json,
    write_static_zone_prior_report_markdown,
)

DEFAULT_OUTPUT_ROOT = "outputs/static_zone_prior_poc"


def run_static_zone_prior_poc(
    dataset_config_path: str | Path,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    experiment_name: str | None = None,
    run_id: str | None = None,
    limit: int | None = None,
    grid_columns: int = 32,
    grid_rows: int = 18,
) -> dict[str, Any]:
    dataset_path = resolve_project_path(dataset_config_path)
    raw_config = load_yaml_config(dataset_path)
    dataset_config = load_dataset_config(dataset_path)
    if limit is not None:
        dataset_config = replace(dataset_config, frame_limit=limit)

    frame_count, frame_size = _inspect_stream(dataset_config)
    annotations = _load_target_annotations(raw_config, dataset_config)
    name = experiment_name or str(raw_config.get("name") or dataset_path.stem)
    suffix = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    selected_run_id = run_id or f"{name}_static_zone_prior_{suffix}"
    run_root = Path(output_root) / selected_run_id
    report_root = run_root / "reports"
    cells_path = run_root / "static_zone_cells.jsonl"
    report_json_path = report_root / "static_zone_prior_report.json"
    report_md_path = report_root / "static_zone_prior_report.md"
    target_classes = _target_classes_from_config(raw_config)

    report, cell_records = build_static_zone_prior_report(
        ground_truth=annotations,
        frame_count=frame_count,
        frame_size=frame_size,
        grid_shape=GridShape(columns=grid_columns, rows=grid_rows),
        profiles=default_static_zone_profiles(),
        dataset_config=project_relative(dataset_path),
        experiment_name=name,
        target_classes=target_classes,
    )
    write_jsonl(cell_records, cells_path)
    write_static_zone_prior_report_json(report, report_json_path)
    write_static_zone_prior_report_markdown(report, report_md_path)

    manifest = {
        "schema_version": 1,
        "pipeline_type": "static_zone_prior_poc",
        "experiment_name": name,
        "run_id": selected_run_id,
        "dataset_config": project_relative(dataset_path),
        "limit": limit,
        "grid_shape": {"columns": grid_columns, "rows": grid_rows},
        "target_classes": list(target_classes),
        "outputs": {
            "cell_records": str(cells_path),
            "report_json": str(report_json_path),
            "report_markdown": str(report_md_path),
        },
        "summary": {
            "frame_count": report.frame_count,
            "target_frame_count": report.target_frame_count,
            "target_gt_count": report.target_gt_count,
            "occupied_cell_count": report.occupied_cell_count,
            "profiles": {
                name: {
                    "selected_area_ratio": profile.selected_area_ratio,
                    "input_area_reduction": profile.input_area_reduction,
                    "center_gt_recall": profile.center_gt_recall,
                    "bbox_gt_recall": profile.bbox_gt_recall,
                    "center_target_frame_recall": profile.center_target_frame_recall,
                    "bbox_target_frame_recall": profile.bbox_target_frame_recall,
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


def _inspect_stream(dataset_config) -> tuple[int, FrameSize]:
    frame_count = 0
    frame_size: FrameSize | None = None
    for packet in create_dataset_stream(dataset_config):
        frame_count += 1
        if frame_size is None:
            frame_size = packet.original_size
        elif packet.original_size != frame_size:
            raise ValueError(
                f"Static zone POC requires fixed frame size: {frame_size} -> {packet.original_size}"
            )
    if frame_size is None:
        raise ValueError("Dataset stream produced no frames.")
    return frame_count, frame_size


def _load_target_annotations(raw_config: dict[str, Any], dataset_config) -> list[GroundTruthAnnotation]:
    loader = create_annotation_loader(raw_config.get("annotations"), dataset_config)
    if loader is None:
        return []
    annotations = loader.load()
    return filter_gt_by_target_classes(annotations, _target_classes_from_config(raw_config))


def _target_classes_from_config(raw_config: dict[str, Any]) -> tuple[str, ...]:
    return tuple(raw_config.get("validation", {}).get("target_classes") or ())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1.3-C static zone prior POC.")
    parser.add_argument("--dataset-config", required=True)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--experiment-name")
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--grid-columns", type=int, default=32)
    parser.add_argument("--grid-rows", type=int, default=18)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run_static_zone_prior_poc(
        dataset_config_path=args.dataset_config,
        output_root=args.output_root,
        experiment_name=args.experiment_name,
        run_id=args.run_id,
        limit=args.limit,
        grid_columns=args.grid_columns,
        grid_rows=args.grid_rows,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
