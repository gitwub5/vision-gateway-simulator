"""Download the Mall Dataset for retail/space analytics validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.datasets.download_common import download_url, extract_zip, write_manifest


MALL_DATASET_URL = "https://personal.ie.cuhk.edu.hk/~ccloy/files/datasets/mall_dataset.zip"
DEFAULT_OUTPUT_ROOT = Path("data/mall_dataset")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Mall Dataset archive.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive_path = args.output_root / "archives" / "mall_dataset.zip"
    download_url(MALL_DATASET_URL, archive_path, force=args.force)
    if args.extract:
        extract_zip(archive_path, args.output_root, force=args.force)
    write_manifest(
        args.output_root / "phase1_3_mall_dataset_manifest.json",
        {
            "dataset": "Mall Dataset",
            "source": "https://personal.ie.cuhk.edu.hk/~ccloy/downloads_mall_dataset.html",
            "archive": str(archive_path),
            "expected_config": "configs/datasets/mall/mall_dataset.yaml",
            "phase1_3_role": "retail/space analytics validation",
            "notes": [
                "Fixed public shopping-mall webcam frames with exhaustive pedestrian head-position labels.",
                "Ground truth is point-based, so ROI validation should use point containment or a documented proxy box.",
            ],
        },
    )


if __name__ == "__main__":
    main()
