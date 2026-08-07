"""Render ROI and detection visualizations from saved experiment outputs."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_loader import create_dataset_stream, load_dataset_config
from data_loader.annotation_loader import read_ground_truth_jsonl
from evaluation import read_detection_jsonl
from gpu_inference.yolo_roi import read_roi_metadata_jsonl
from visualization import render_visualizations


def main() -> None:
    args = _parse_args()
    dataset_config = load_dataset_config(args.dataset_config)
    if args.frame_limit is not None:
        dataset_config = replace(dataset_config, frame_limit=args.frame_limit)

    stream = create_dataset_stream(dataset_config)
    summary = render_visualizations(
        frames=stream,
        roi_records=read_roi_metadata_jsonl(args.roi_metadata),
        full_frame_detections=read_detection_jsonl(args.full_frame_detections),
        roi_detections=read_detection_jsonl(args.roi_detections),
        ground_truth=read_ground_truth_jsonl(args.ground_truth) if args.ground_truth else None,
        output_root=args.output_root,
        limit=args.render_limit,
        iou_threshold=args.iou_threshold,
    )

    print(summary.to_json_dict())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render ROI and detection visualization images.")
    parser.add_argument("--dataset-config", default="configs/datasets/default.yaml")
    parser.add_argument("--roi-metadata", default="outputs/roi_metadata/rule_roi.jsonl")
    parser.add_argument("--full-frame-detections", default="outputs/detections/full_frame.jsonl")
    parser.add_argument("--roi-detections", default="outputs/detections/roi_yolo.jsonl")
    parser.add_argument("--ground-truth", default=None)
    parser.add_argument("--output-root", default="outputs/visualizations")
    parser.add_argument("--frame-limit", type=int, default=None)
    parser.add_argument("--render-limit", type=int, default=None)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    return parser.parse_args()


if __name__ == "__main__":
    main()
