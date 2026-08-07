"""Run rule-based ROI generator and write metadata outputs."""

from __future__ import annotations

import argparse
import sys
from itertools import islice
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_loader import create_dataset_stream, load_dataset_config
from roi_generator import (
    GateFrameMetadataWriter,
    ROIMetadataWriter,
    RuleBasedRoiGenerator,
    frame_metadata_from_gate_decision,
    load_roi_generator_config,
    roi_metadata_from_gate_decision,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run rule-based ROI generator metadata generation.")
    parser.add_argument("--dataset-config", default="configs/datasets/default.yaml", help="Path to dataset YAML config.")
    parser.add_argument(
        "--roi-generator-config",
        default="configs/roi_generator/default.yaml",
        help="Path to ROI generator YAML config.",
    )
    parser.add_argument("--gate-config", dest="roi_generator_config", help=argparse.SUPPRESS)
    parser.add_argument(
        "--roi-output",
        default="outputs/roi_metadata/rule_roi.jsonl",
        help="Output JSONL path for ROI metadata records.",
    )
    parser.add_argument(
        "--frame-output",
        default="outputs/roi_metadata/gate_decisions.jsonl",
        help="Output JSONL path for frame-level ROI generator decisions.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of frames to process.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_config = load_dataset_config(args.dataset_config)
    roi_generator_config = load_roi_generator_config(args.roi_generator_config)

    stream = create_dataset_stream(dataset_config)
    generator = RuleBasedRoiGenerator(roi_generator_config)
    roi_writer = ROIMetadataWriter(args.roi_output)
    frame_writer = GateFrameMetadataWriter(args.frame_output)

    processed_frames = 0
    roi_records_count = 0
    iterable = islice(stream, args.limit) if args.limit is not None else stream

    for packet in iterable:
        decision = generator.process(packet)
        roi_records = roi_metadata_from_gate_decision(decision)
        frame_record = frame_metadata_from_gate_decision(decision)

        roi_writer.write_many(roi_records)
        frame_writer.write(frame_record)

        processed_frames += 1
        roi_records_count += len(roi_records)

    print(
        {
            "processed_frames": processed_frames,
            "roi_records": roi_records_count,
            "roi_output": args.roi_output,
            "frame_output": args.frame_output,
        }
    )


if __name__ == "__main__":
    main()
