"""Inspect dataset stream packets from a dataset config."""

from __future__ import annotations

import argparse
import sys
from itertools import islice
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_loader import create_dataset_stream, load_dataset_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect FramePacket output from dataset loader.")
    parser.add_argument("--config", default="configs/datasets/default.yaml", help="Path to dataset YAML config.")
    parser.add_argument("--limit", type=int, default=5, help="Number of packets to print.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_dataset_config(args.config)
    stream = create_dataset_stream(config)

    for packet in islice(stream, args.limit):
        print(
            {
                "camera_id": packet.camera_id,
                "frame_id": packet.frame_id,
                "timestamp": packet.timestamp,
                "original_size": packet.original_size.as_list(),
            }
        )


if __name__ == "__main__":
    main()
