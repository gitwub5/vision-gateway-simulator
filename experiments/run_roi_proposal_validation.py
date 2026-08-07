"""Run target-aware ROI proposal validation without downstream model inference."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
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
from evaluation import collect_hardware_snapshot
from evaluation.roi_proposal_report import (
    RoiProposalInputs,
    build_roi_proposal_report,
    write_roi_proposal_report_json,
    write_roi_proposal_report_markdown,
)
from gpu_inference.yolo_roi import read_gate_frame_metadata_jsonl, read_roi_metadata_jsonl
from roi_generator import load_roi_generator_config
from experiments.validation_common import load_validation_config, run_roi_generator_metadata, write_json
from visualization.roi_proposal_renderer import render_roi_failure_visualizations


PIPELINE_TYPE = "roi_proposal_validation"
DEFAULT_OUTPUT_ROOT = "outputs/roi_proposal_validation"


class RoiProposalPaths:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.roi_metadata_dir = root / "roi_metadata"
        self.annotations_dir = root / "annotations"
        self.reports_dir = root / "reports"
        self.visualizations_dir = root / "visualizations"
        self.failures_dir = self.visualizations_dir / "failures"
        self.cache = root / "cache"
        self.manifest = root / "manifest.json"
        self.roi_metadata = self.roi_metadata_dir / "rule_roi.jsonl"
        self.frame_metadata = self.roi_metadata_dir / "gate_decisions.jsonl"
        self.ground_truth = self.annotations_dir / "ground_truth.jsonl"
        self.report_json = self.reports_dir / "roi_proposal_report.json"
        self.report_markdown = self.reports_dir / "roi_proposal_report.md"

    @classmethod
    def from_root(cls, root: str | Path) -> "RoiProposalPaths":
        return cls(Path(root))

    def mkdirs(self) -> None:
        for path in [
            self.roi_metadata_dir,
            self.annotations_dir,
            self.reports_dir,
            self.failures_dir,
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
            "report_json": str(self.report_json),
            "report_markdown": str(self.report_markdown),
            "visualizations": str(self.visualizations_dir),
        }


def main() -> None:
    args = parse_args()
    started_at = datetime.now().astimezone()
    experiment_name = args.experiment_name or "roi_proposal_sample"
    run_id = args.run_id or make_run_id(started_at, experiment_name)
    output_root = Path(args.output_root) / run_id
    paths = RoiProposalPaths.from_root(output_root)
    paths.mkdirs()

    os.environ.setdefault("MPLCONFIGDIR", str(paths.cache / "matplotlib"))

    total_started = perf_counter()
    stage_timings: dict[str, float] = {}

    dataset_config = load_dataset_config(args.dataset_config)
    if args.limit is not None:
        dataset_config = replace(dataset_config, frame_limit=args.limit)
    annotation_config = load_annotation_config(args.dataset_config)
    if not annotation_config or str(annotation_config.get("type", "")).lower() in {"", "none", "null"}:
        raise ValueError("ROI proposal validation requires enabled dataset annotations.")
    validation_config = load_validation_config(args.dataset_config)
    target_classes = tuple(str(item) for item in validation_config.get("target_classes", []) if item is not None)
    roi_generator_config = load_roi_generator_config(args.roi_generator_config)

    def timed(stage_name: str, func):
        started = perf_counter()
        result = func()
        stage_timings[stage_name] = perf_counter() - started
        return result

    gt_summary = timed(
        "ground_truth",
        lambda: run_ground_truth(
            annotation_config=annotation_config,
            dataset_config=dataset_config,
            output_path=paths.ground_truth,
        ),
    )
    roi_generator_summary = timed(
        "roi_generator_metadata",
        lambda: run_roi_generator_metadata(
            dataset_config=dataset_config,
            roi_generator_config=roi_generator_config,
            roi_output=paths.roi_metadata,
            frame_output=paths.frame_metadata,
        ),
    )
    report_summary = timed(
        "roi_proposal_report",
        lambda: run_report(paths=paths, target_classes=target_classes),
    )
    visualization_summary = None
    if not args.skip_visualization:
        visualization_summary = timed(
            "visualization",
            lambda: render_roi_failure_visualizations(
                frames=create_dataset_stream(dataset_config),
                roi_records=read_roi_metadata_jsonl(paths.roi_metadata),
                frame_records=read_gate_frame_metadata_jsonl(paths.frame_metadata),
                ground_truth=read_ground_truth_jsonl(paths.ground_truth),
                output_dir=paths.failures_dir,
                render_limit=args.render_limit,
                target_classes=target_classes,
                roi_too_large_ratio=args.roi_too_large_ratio,
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
            "roi_generator_config": args.roi_generator_config,
            "limit": args.limit,
            "render_limit": args.render_limit,
            "target_classes": list(target_classes),
            "roi_too_large_ratio": args.roi_too_large_ratio,
        },
        "hardware": collect_hardware_snapshot(),
        "outputs": paths.to_json_dict(),
        "summaries": {
            "ground_truth": gt_summary,
            "roi_generator": roi_generator_summary,
            "roi_proposal": report_summary,
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


def run_ground_truth(annotation_config, dataset_config, output_path: Path) -> dict[str, Any]:
    loader = create_annotation_loader(annotation_config, dataset_config)
    if loader is None:
        raise ValueError("ROI proposal validation requires a ground-truth annotation loader.")
    records = loader.load()
    write_ground_truth_jsonl(records, output_path)
    return {
        "gt_count": len(records),
        "frames_with_gt": len({(record.camera_id, record.frame_id) for record in records}),
    }


def run_report(paths: RoiProposalPaths, target_classes: tuple[str, ...]) -> dict[str, Any]:
    inputs = RoiProposalInputs(
        ground_truth=paths.ground_truth,
        roi_metadata=paths.roi_metadata,
        frame_metadata=paths.frame_metadata,
        report_json=paths.report_json,
        report_markdown=paths.report_markdown,
    )
    report = build_roi_proposal_report(
        inputs=inputs,
        ground_truth=read_ground_truth_jsonl(paths.ground_truth),
        roi_records=read_roi_metadata_jsonl(paths.roi_metadata),
        frame_records=read_gate_frame_metadata_jsonl(paths.frame_metadata),
        target_classes=target_classes,
    )
    write_roi_proposal_report_json(report, paths.report_json)
    write_roi_proposal_report_markdown(report, paths.report_markdown)
    return report.to_json_dict()


def make_run_id(started_at: datetime, experiment_name: str) -> str:
    safe_name = experiment_name.replace("/", "_").replace(" ", "_")
    if not safe_name.startswith("roi_proposal_"):
        safe_name = f"roi_proposal_{safe_name}"
    return f"{started_at.strftime('%Y%m%d_%H%M%S')}_{safe_name}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run target-aware ROI proposal validation.")
    parser.add_argument("--dataset-config", required=True)
    parser.add_argument("--roi-generator-config", default="configs/roi_generator/profile_balanced.yaml")
    parser.add_argument("--gate-config", dest="roi_generator_config", help=argparse.SUPPRESS)
    parser.add_argument("--experiment-name", default=None)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--render-limit", type=int, default=30)
    parser.add_argument("--roi-too-large-ratio", type=float, default=0.30)
    parser.add_argument("--skip-visualization", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
