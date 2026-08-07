"""Run ROI-gated end-to-end model inference validation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_loader import create_dataset_stream, load_dataset_config
from data_loader.annotation_loader import (
    create_annotation_loader,
    load_annotation_config,
    read_ground_truth_jsonl,
    write_ground_truth_jsonl,
)
from evaluation import (
    AnnotationQuality,
    ComparisonInputs,
    GtReportInputs,
    build_gt_report,
    build_comparison_report,
    collect_hardware_snapshot,
    read_detection_jsonl,
    write_gt_report_json,
    write_gt_report_markdown,
    write_report_json,
    write_report_markdown,
)
from gpu_inference.yolo_full_frame import (
    FullFrameYoloRunner,
    load_yolo_config,
    write_detection_jsonl,
    write_metrics_json,
)
from gpu_inference.yolo_roi import (
    RoiYoloRunner,
    read_gate_frame_metadata_jsonl,
    read_roi_metadata_jsonl,
    write_roi_metrics_json,
)
from npx_emulator import load_npx_gate_config
from experiments.validation_common import load_validation_config, run_gate_metadata, write_json
from visualization import render_visualizations


PIPELINE_TYPE = "e2e_inference_validation"
DEFAULT_OUTPUT_ROOT = "outputs/e2e_inference_validation"


def main() -> None:
    args = parse_args()
    started_at = datetime.now().astimezone()
    experiment_name = resolve_experiment_name(args)
    run_id = args.run_id or make_run_id(started_at, experiment_name)
    output_root = Path(args.output_root) / run_id
    paths = ExperimentPaths.from_root(output_root)
    paths.mkdirs()

    os.environ.setdefault("YOLO_CONFIG_DIR", str(paths.cache / "ultralytics"))
    os.environ.setdefault("MPLCONFIGDIR", str(paths.cache / "matplotlib"))

    stage_timings: dict[str, float] = {}
    total_started = perf_counter()

    dataset_config = load_dataset_config(args.dataset_config)
    if args.limit is not None:
        dataset_config = replace(dataset_config, frame_limit=args.limit)
    annotation_config = load_annotation_config(args.dataset_config)
    validation_config = load_validation_config(args.dataset_config)
    target_classes = tuple(str(item) for item in validation_config.get("target_classes", []) if item is not None)
    annotation_type = str((annotation_config or {}).get("type", "")).lower()
    gt_validation_enabled = bool(
        annotation_config
        and annotation_config.get("enabled", True)
        and annotation_type not in {"", "none", "null"}
    )
    if args.disable_gt_validation:
        gt_validation_enabled = False
    gate_config = load_npx_gate_config(args.gate_config)
    yolo_config, _ = load_yolo_config(args.yolo_config)
    if args.model is not None:
        yolo_config = replace(yolo_config, model=args.model)

    def timed(stage_name: str, func):
        started = perf_counter()
        result = func()
        stage_timings[stage_name] = perf_counter() - started
        return result

    gate_summary = timed(
        "roi_gate_metadata",
        lambda: run_gate_metadata(
            dataset_config=dataset_config,
            gate_config=gate_config,
            roi_output=paths.roi_metadata,
            frame_output=paths.frame_metadata,
        ),
    )

    full_summary = timed(
        "full_frame_yolo",
        lambda: run_full_frame_yolo(
            dataset_config=dataset_config,
            yolo_config=yolo_config,
            detections_output=paths.full_frame_detections,
            metrics_output=paths.full_frame_metrics,
        ),
    )

    roi_summary = timed(
        "roi_yolo",
        lambda: run_roi_yolo(
            dataset_config=dataset_config,
            yolo_config=yolo_config,
            roi_metadata=paths.roi_metadata,
            frame_metadata=paths.frame_metadata,
            detections_output=paths.roi_detections,
            metrics_output=paths.roi_metrics,
            include_full_frame_checks=not args.disable_full_frame_checks,
        ),
    )

    comparison_summary = timed(
        "comparison_report",
        lambda: run_comparison(
            paths=paths,
            iou_threshold=args.iou_threshold,
        ),
    )

    gt_summary = None
    if gt_validation_enabled:
        gt_summary = timed(
            "gt_validation",
            lambda: run_gt_validation(
                dataset_config=dataset_config,
                annotation_config=annotation_config,
                paths=paths,
                iou_threshold=args.iou_threshold,
                target_classes=target_classes,
            ),
        )

    visualization_summary = None
    if not args.skip_visualization:
        visualization_summary = timed(
            "visualization",
            lambda: run_visualization(
                dataset_config=dataset_config,
                paths=paths,
                render_limit=args.render_limit,
                iou_threshold=args.iou_threshold,
                include_gt=gt_validation_enabled,
            ),
        )

    total_seconds = perf_counter() - total_started
    finished_at = datetime.now().astimezone()
    manifest = {
        "schema_version": 1,
        "pipeline_type": PIPELINE_TYPE,
        "run_id": run_id,
        "experiment_name": experiment_name,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "total_seconds": total_seconds,
        "stage_seconds": stage_timings,
        "inputs": {
            "pipeline_type": PIPELINE_TYPE,
            "dataset_config": args.dataset_config,
            "gate_config": args.gate_config,
            "yolo_config": args.yolo_config,
            "limit": args.limit,
            "render_limit": args.render_limit,
            "iou_threshold": args.iou_threshold,
            "include_full_frame_checks": not args.disable_full_frame_checks,
            "gt_validation_enabled": gt_validation_enabled,
            "target_classes": list(target_classes),
        },
        "hardware": collect_hardware_snapshot(),
        "outputs": paths.to_json_dict(),
        "summaries": {
            "gate": gate_summary,
            "full_frame_yolo": full_summary,
            "roi_yolo": roi_summary,
            "comparison": comparison_summary,
            "gt_validation": gt_summary,
            "visualization": visualization_summary,
        },
    }
    write_json(manifest, paths.manifest)
    print(
        json.dumps(
            {
                "pipeline_type": PIPELINE_TYPE,
                "run_id": run_id,
                "output_root": str(output_root),
                "total_seconds": total_seconds,
            },
            indent=2,
        )
    )


class ExperimentPaths:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.roi_metadata_dir = root / "roi_metadata"
        self.detections_dir = root / "detections"
        self.annotations_dir = root / "annotations"
        self.reports_dir = root / "reports"
        self.visualizations_dir = root / "visualizations"
        self.cache = root / "cache"
        self.manifest = root / "manifest.json"
        self.roi_metadata = self.roi_metadata_dir / "rule_roi.jsonl"
        self.frame_metadata = self.roi_metadata_dir / "gate_decisions.jsonl"
        self.ground_truth = self.annotations_dir / "ground_truth.jsonl"
        self.full_frame_detections = self.detections_dir / "full_frame.jsonl"
        self.roi_detections = self.detections_dir / "roi_yolo.jsonl"
        self.full_frame_metrics = self.reports_dir / "full_frame_metrics.json"
        self.roi_metrics = self.reports_dir / "roi_yolo_metrics.json"
        self.comparison_json = self.reports_dir / "comparison_report.json"
        self.comparison_markdown = self.reports_dir / "comparison_report.md"
        self.gt_report_json = self.reports_dir / "gt_report.json"
        self.gt_report_markdown = self.reports_dir / "gt_report.md"

    @classmethod
    def from_root(cls, root: str | Path) -> "ExperimentPaths":
        return cls(Path(root))

    def mkdirs(self) -> None:
        for path in [
            self.roi_metadata_dir,
            self.detections_dir,
            self.annotations_dir,
            self.reports_dir,
            self.visualizations_dir,
            self.cache,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def to_json_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "manifest": str(self.manifest),
            "roi_metadata": str(self.roi_metadata),
            "frame_metadata": str(self.frame_metadata),
            "ground_truth": str(self.ground_truth),
            "full_frame_detections": str(self.full_frame_detections),
            "roi_detections": str(self.roi_detections),
            "full_frame_metrics": str(self.full_frame_metrics),
            "roi_metrics": str(self.roi_metrics),
            "comparison_json": str(self.comparison_json),
            "comparison_markdown": str(self.comparison_markdown),
            "gt_report_json": str(self.gt_report_json),
            "gt_report_markdown": str(self.gt_report_markdown),
            "visualizations": str(self.visualizations_dir),
        }


def run_full_frame_yolo(dataset_config, yolo_config, detections_output: Path, metrics_output: Path) -> dict[str, Any]:
    runner = FullFrameYoloRunner.from_config(yolo_config)
    detections = runner.run(create_dataset_stream(dataset_config))
    write_detection_jsonl(detections, detections_output)
    write_metrics_json(runner.last_metrics, metrics_output)
    return {
        "detection_count": len(detections),
        "metrics": runner.last_metrics.to_json_dict(),
    }


def run_roi_yolo(
    dataset_config,
    yolo_config,
    roi_metadata: Path,
    frame_metadata: Path,
    detections_output: Path,
    metrics_output: Path,
    include_full_frame_checks: bool,
) -> dict[str, Any]:
    runner = RoiYoloRunner.from_config(yolo_config)
    frame_records = read_gate_frame_metadata_jsonl(frame_metadata) if include_full_frame_checks else []
    detections = runner.run(
        frames=create_dataset_stream(dataset_config),
        roi_records=read_roi_metadata_jsonl(roi_metadata),
        frame_records=frame_records,
        include_full_frame_checks=include_full_frame_checks,
    )
    write_detection_jsonl(detections, detections_output)
    write_roi_metrics_json(runner.last_metrics, metrics_output)
    return {
        "detection_count": len(detections),
        "metrics": runner.last_metrics.to_json_dict(),
    }


def run_comparison(paths: ExperimentPaths, iou_threshold: float) -> dict[str, Any]:
    inputs = ComparisonInputs(
        full_frame_detections=paths.full_frame_detections,
        roi_detections=paths.roi_detections,
        full_frame_metrics=paths.full_frame_metrics,
        roi_metrics=paths.roi_metrics,
        roi_metadata=paths.roi_metadata,
        frame_metadata=paths.frame_metadata,
        report_json=paths.comparison_json,
        report_markdown=paths.comparison_markdown,
    )
    report = build_comparison_report(inputs, iou_threshold=iou_threshold)
    write_report_json(report, paths.comparison_json)
    write_report_markdown(report, paths.comparison_markdown)
    return report.to_json_dict()


def run_gt_validation(
    dataset_config,
    annotation_config,
    paths: ExperimentPaths,
    iou_threshold: float,
    target_classes: tuple[str, ...] = (),
) -> dict[str, Any]:
    loader = create_annotation_loader(annotation_config, dataset_config)
    if loader is None:
        return {"enabled": False}
    ground_truth = loader.load()
    write_ground_truth_jsonl(ground_truth, paths.ground_truth)
    inputs = GtReportInputs(
        ground_truth=paths.ground_truth,
        full_frame_detections=paths.full_frame_detections,
        roi_detections=paths.roi_detections,
        roi_metadata=paths.roi_metadata,
        report_json=paths.gt_report_json,
        report_markdown=paths.gt_report_markdown,
    )
    report = build_gt_report(
        inputs=inputs,
        ground_truth=ground_truth,
        full_frame_detections=read_detection_jsonl(paths.full_frame_detections),
        roi_detections=read_detection_jsonl(paths.roi_detections),
        iou_threshold=iou_threshold,
        annotation_quality=AnnotationQuality.from_mapping(annotation_config.get("quality")),
        target_classes=target_classes,
    )
    write_gt_report_json(report, paths.gt_report_json)
    write_gt_report_markdown(report, paths.gt_report_markdown)
    return report.to_json_dict()


def run_visualization(
    dataset_config,
    paths: ExperimentPaths,
    render_limit: int | None,
    iou_threshold: float,
    include_gt: bool = False,
) -> dict:
    summary = render_visualizations(
        frames=create_dataset_stream(dataset_config),
        roi_records=read_roi_metadata_jsonl(paths.roi_metadata),
        full_frame_detections=read_detection_jsonl(paths.full_frame_detections),
        roi_detections=read_detection_jsonl(paths.roi_detections),
        ground_truth=read_ground_truth_jsonl(paths.ground_truth) if include_gt and paths.ground_truth.exists() else None,
        output_root=paths.visualizations_dir,
        limit=render_limit,
        iou_threshold=iou_threshold,
    )
    return summary.to_json_dict()


def make_run_id(started_at: datetime, experiment_name: str) -> str:
    safe_name = experiment_name.replace("/", "_").replace(" ", "_")
    if not safe_name.startswith("e2e_"):
        safe_name = f"e2e_{safe_name}"
    return f"{started_at.strftime('%Y%m%d_%H%M%S')}_{safe_name}"


def resolve_experiment_name(args: argparse.Namespace) -> str:
    if args.experiment_name:
        return args.experiment_name
    if args.dataset_name:
        return args.dataset_name
    return "e2e_sample"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ROI-gated end-to-end inference validation.")
    parser.add_argument("--dataset-config", default="configs/dataset.yaml")
    parser.add_argument("--gate-config", default="configs/npx_gate.yaml")
    parser.add_argument("--yolo-config", default="configs/yolo.yaml")
    parser.add_argument("--experiment-name", default=None)
    parser.add_argument("--dataset-name", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--render-limit", type=int, default=30)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--model", default=None)
    parser.add_argument("--disable-full-frame-checks", action="store_true")
    parser.add_argument("--disable-gt-validation", action="store_true")
    parser.add_argument("--skip-visualization", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
