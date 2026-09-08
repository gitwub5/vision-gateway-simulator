"""Download MOTChallenge MOT17 data for Phase 1.3 surveillance validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.datasets.download_common import download_url, extract_zip, write_manifest


MOT17_URL = "https://motchallenge.net/data/MOT17.zip"
MOT17_LABELS_URL = "https://motchallenge.net/data/MOT17Labels.zip"
DEFAULT_OUTPUT_ROOT = Path("data/motchallenge")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download MOT17 archives.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--sequence", default="MOT17-04", help="Phase 1.3 selected sequence.")
    parser.add_argument("--download-images", action="store_true", help="Download full MOT17.zip (about 5.5 GB).")
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive_dir = args.output_root / "archives"
    labels_archive = download_url(MOT17_LABELS_URL, archive_dir / "MOT17Labels.zip", force=args.force)
    image_archive = None
    if args.download_images:
        image_archive = download_url(MOT17_URL, archive_dir / "MOT17.zip", force=args.force)
    else:
        print("Skipped MOT17.zip. Re-run with --download-images for frame images.")

    if args.extract:
        extract_zip(labels_archive, args.output_root, force=args.force)
        if image_archive is not None:
            extract_zip(image_archive, args.output_root, force=args.force)

    write_manifest(
        args.output_root / "phase1_3_mot17_manifest.json",
        {
            "dataset": "MOT17",
            "selected_sequence": args.sequence,
            "source": "https://motchallenge.net/data/MOT17/",
            "labels_archive": str(labels_archive),
            "image_archive": str(image_archive) if image_archive else None,
            "expected_config": f"configs/datasets/motchallenge/{args.sequence.lower().replace('-', '_')}.yaml",
            "notes": [
                "Use MOT17-04 for surveillance/security Phase 1.3 validation.",
                "MOT17Labels.zip alone is not enough for ROI validation; frame images require MOT17.zip.",
            ],
        },
    )


if __name__ == "__main__":
    main()
