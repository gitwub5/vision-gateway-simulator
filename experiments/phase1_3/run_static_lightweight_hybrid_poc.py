"""Run Phase 1.3-K static zone prior + budgeted lightweight visual priority hybrid validation."""

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

from common import FrameSize, GroundTruthAnnotation
from common.io import load_yaml_config, write_json, write_jsonl
from data_loader.annotation_loader import create_annotation_loader
from data_loader.dataset_stream import create_dataset_stream, load_dataset_config
from evaluation.metrics.class_filter import filter_gt_by_target_classes
from evaluation.reports.static_lightweight_hybrid import (
    GridShape,
    StaticLightweightFrameScores,
    build_static_lightweight_report,
    default_static_lightweight_profiles,
    write_static_lightweight_report_json,
    write_static_lightweight_report_markdown,
)

DEFAULT_OUTPUT_ROOT = "outputs/static_lightweight_hybrid_poc"


def run_static_lightweight_hybrid_poc(
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

    grid_shape = GridShape(columns=grid_columns, rows=grid_rows)
    frame_scores, frame_size = _compute_frame_signal_scores(dataset_config, grid_shape)
    annotations = _load_target_annotations(raw_config, dataset_config)
    target_classes = _target_classes_from_config(raw_config)
    name = experiment_name or str(raw_config.get("name") or dataset_path.stem)
    suffix = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    selected_run_id = run_id or f"{name}_static_lightweight_hybrid_{suffix}"
    run_root = Path(output_root) / selected_run_id
    report_root = run_root / "reports"
    frame_records_path = run_root / "static_lightweight_hybrid_frames.jsonl"
    report_json_path = report_root / "static_lightweight_hybrid_report.json"
    report_md_path = report_root / "static_lightweight_hybrid_report.md"

    report, frame_records = build_static_lightweight_report(
        frame_scores=frame_scores,
        ground_truth=annotations,
        profiles=default_static_lightweight_profiles(),
        grid_shape=grid_shape,
        frame_size=frame_size,
        dataset_config=project_relative(dataset_path),
        experiment_name=name,
        target_classes=target_classes,
    )
    write_jsonl(frame_records, frame_records_path)
    write_static_lightweight_report_json(report, report_json_path)
    write_static_lightweight_report_markdown(report, report_md_path)

    manifest = {
        "schema_version": 1,
        "pipeline_type": "static_lightweight_hybrid_poc",
        "experiment_name": name,
        "run_id": selected_run_id,
        "dataset_config": project_relative(dataset_path),
        "limit": limit,
        "grid_shape": grid_shape.to_json_dict(),
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
                    "static_selected_area_ratio": profile.static_selected_area_ratio,
                    "selected_area_ratio": profile.selected_area_ratio,
                    "input_area_reduction": profile.input_area_reduction,
                    "center_gt_recall": profile.center_gt_recall,
                    "bbox_gt_recall": profile.bbox_gt_recall,
                    "static_only_bbox_gt_recall": profile.static_only_bbox_gt_recall,
                    "incremental_bbox_gt_recall": profile.incremental_bbox_gt_recall,
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


def _compute_frame_signal_scores(
    dataset_config, grid_shape: GridShape
) -> tuple[list[StaticLightweightFrameScores], FrameSize]:
    cv2 = _require_cv2()
    records: list[StaticLightweightFrameScores] = []
    frame_size: FrameSize | None = None
    for frame_index, packet in enumerate(create_dataset_stream(dataset_config)):
        if frame_size is None:
            frame_size = packet.original_size
        elif packet.original_size != frame_size:
            raise ValueError(
                f"Static lightweight hybrid POC requires fixed frame size: {frame_size} -> {packet.original_size}"
            )
        gray = _to_gray(packet.frame, cv2)
        edge_map = cv2.Canny(gray, 50, 150)
        laplacian = cv2.Laplacian(gray, cv2.CV_32F)
        edge_scores = _cell_means(edge_map, grid_shape)
        texture_scores = _cell_stddev(gray, grid_shape)
        laplacian_scores = _cell_abs_means(laplacian, grid_shape)
        texture_signal = _normalize_scores([
            (texture + laplace) / 2.0
            for texture, laplace in zip(
                _normalize_scores(texture_scores),
                _normalize_scores(laplacian_scores),
                strict=True,
            )
        ])
        edge_signal = _normalize_scores(edge_scores)
        hybrid_signal = _normalize_scores([
            (edge * 0.55) + (texture * 0.45)
            for edge, texture in zip(edge_signal, texture_signal, strict=True)
        ])
        records.append(
            StaticLightweightFrameScores(
                camera_id=packet.camera_id,
                frame_id=packet.frame_id,
                frame_index=frame_index,
                frame_size=packet.original_size,
                scores_by_signal={
                    "edge": tuple(edge_signal),
                    "texture": tuple(texture_signal),
                    "hybrid": tuple(hybrid_signal),
                },
            )
        )
    if not records or frame_size is None:
        raise ValueError("Dataset stream produced no frames.")
    return records, frame_size


def _load_target_annotations(raw_config: dict[str, Any], dataset_config) -> list[GroundTruthAnnotation]:
    loader = create_annotation_loader(raw_config.get("annotations"), dataset_config)
    if loader is None:
        return []
    annotations = loader.load()
    return filter_gt_by_target_classes(annotations, _target_classes_from_config(raw_config))


def _target_classes_from_config(raw_config: dict[str, Any]) -> tuple[str, ...]:
    return tuple(raw_config.get("validation", {}).get("target_classes") or ())


def _to_gray(frame, cv2):
    if len(frame.shape) == 2:
        return frame
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _cell_means(image, grid_shape: GridShape) -> list[float]:
    return [_cell_stat(image, grid_shape, row, column, "mean") for row, column in _all_cells(grid_shape)]


def _cell_abs_means(image, grid_shape: GridShape) -> list[float]:
    return [_cell_stat(image, grid_shape, row, column, "abs_mean") for row, column in _all_cells(grid_shape)]


def _cell_stddev(image, grid_shape: GridShape) -> list[float]:
    return [_cell_stat(image, grid_shape, row, column, "std") for row, column in _all_cells(grid_shape)]


def _cell_stat(image, grid_shape: GridShape, row: int, column: int, mode: str) -> float:
    np = _require_numpy()
    height, width = image.shape[:2]
    y1 = round(row * height / grid_shape.rows)
    y2 = round((row + 1) * height / grid_shape.rows)
    x1 = round(column * width / grid_shape.columns)
    x2 = round((column + 1) * width / grid_shape.columns)
    cell = image[y1:y2, x1:x2]
    if cell.size == 0:
        return 0.0
    if mode == "mean":
        return float(np.mean(cell))
    if mode == "abs_mean":
        return float(np.mean(np.abs(cell)))
    if mode == "std":
        return float(np.std(cell))
    raise ValueError(f"Unsupported cell stat mode: {mode}")


def _normalize_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    min_score = min(scores)
    max_score = max(scores)
    if max_score <= min_score:
        return [0.0 for _ in scores]
    return [(score - min_score) / (max_score - min_score) for score in scores]


def _all_cells(grid_shape: GridShape) -> list[tuple[int, int]]:
    return [
        (row, column)
        for row in range(grid_shape.rows)
        for column in range(grid_shape.columns)
    ]


def _require_cv2():
    try:
        import cv2
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "OpenCV is required for static lightweight hybrid POC. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return cv2


def _require_numpy():
    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "NumPy is required for static lightweight hybrid POC. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase 1.3-K static zone prior + budgeted lightweight visual priority hybrid POC."
    )
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
    manifest = run_static_lightweight_hybrid_poc(
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
