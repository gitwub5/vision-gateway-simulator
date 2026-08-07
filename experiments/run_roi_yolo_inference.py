"""Run ROI crop YOLO inference from saved ROI metadata."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_loader import create_dataset_stream, load_dataset_config
from gpu_inference.yolo_full_frame import load_model_config, write_detection_jsonl
from gpu_inference.yolo_roi import (
    RoiYoloRunner,
    read_gate_frame_metadata_jsonl,
    read_roi_metadata_jsonl,
    write_roi_metrics_json,
)


def main() -> None:
    args = _parse_args()

    dataset_config = load_dataset_config(args.dataset_config)
    if args.limit is not None:
        dataset_config = replace(dataset_config, frame_limit=args.limit)

    model_config, output_paths = load_model_config(args.model_config)
    if args.model is not None:
        model_config = replace(model_config, model=args.model)

    roi_records = read_roi_metadata_jsonl(args.roi_metadata)
    frame_records = (
        []
        if args.disable_full_frame_checks
        else read_gate_frame_metadata_jsonl(args.frame_metadata)
    )

    stream = create_dataset_stream(dataset_config)
    runner = RoiYoloRunner.from_config(model_config)
    detections = runner.run(
        frames=stream,
        roi_records=roi_records,
        frame_records=frame_records,
        include_full_frame_checks=not args.disable_full_frame_checks,
    )

    detection_path = args.detections_output or output_paths.roi_detections
    metrics_path = args.metrics_output or output_paths.roi_metrics
    write_detection_jsonl(detections, detection_path)
    write_roi_metrics_json(runner.last_metrics, metrics_path)

    print(f"Wrote {len(detections)} detections to {detection_path}")
    print(f"Wrote ROI YOLO metrics to {metrics_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run YOLOv8 inference on saved ROI crops.")
    parser.add_argument("--dataset-config", default="configs/datasets/default.yaml")
    parser.add_argument("--model-config", default="configs/models/yolo_default.yaml")
    parser.add_argument("--yolo-config", dest="model_config", help=argparse.SUPPRESS)
    parser.add_argument("--roi-metadata", default="outputs/roi_metadata/rule_roi.jsonl")
    parser.add_argument("--frame-metadata", default="outputs/roi_metadata/gate_decisions.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--detections-output", default=None)
    parser.add_argument("--metrics-output", default=None)
    parser.add_argument("--disable-full-frame-checks", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
