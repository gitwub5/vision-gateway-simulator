"""Prepare MOTChallenge MOT17Det data for Phase 1.3 surveillance validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.datasets.download_common import download_url, extract_zip_prefix, write_manifest


MOT17DET_URL = "https://motchallenge.net/data/MOT17Det.zip"
MOT17DET_LABELS_URL = "https://motchallenge.net/data/MOT17DetLabels.zip"
DEFAULT_OUTPUT_ROOT = Path("data/motchallenge")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download or unpack MOT17Det archives.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--sequence", default="MOT17-04", help="Phase 1.3 selected sequence.")
    parser.add_argument("--split", default="train", choices=["train", "test"])
    parser.add_argument("--images-archive", type=Path, default=None, help="Already downloaded MOT17Det.zip.")
    parser.add_argument("--labels-archive", type=Path, default=None, help="Already downloaded MOT17DetLabels.zip.")
    parser.add_argument("--download-images", action="store_true", help="Download full MOT17Det.zip.")
    parser.add_argument("--download-labels", action="store_true", help="Download MOT17DetLabels.zip.")
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive_dir = args.output_root / "archives"
    labels_archive = args.labels_archive
    image_archive = args.images_archive
    if args.download_labels:
        labels_archive = download_url(
            MOT17DET_LABELS_URL,
            archive_dir / "MOT17DetLabels.zip",
            force=args.force,
        )
    if args.download_images:
        image_archive = download_url(MOT17DET_URL, archive_dir / "MOT17Det.zip", force=args.force)

    if image_archive is None:
        print("No MOT17Det image archive configured. Pass --images-archive or --download-images.")
    if labels_archive is None:
        print("No MOT17Det label archive configured. Pass --labels-archive or --download-labels.")

    if args.extract:
        if image_archive is None or labels_archive is None:
            raise SystemExit("--extract requires both --images-archive and --labels-archive, or download flags.")
        prefix = f"{args.split}/{args.sequence}"
        extract_zip_prefix(image_archive, args.output_root, prefix, force=args.force)
        extract_zip_prefix(labels_archive, args.output_root, prefix, force=args.force)

    write_manifest(
        args.output_root / "phase1_3_mot17_manifest.json",
        {
            "dataset": "MOT17Det",
            "selected_sequence": args.sequence,
            "split": args.split,
            "source": "https://motchallenge.net/data/MOT17Det/",
            "labels_archive": str(labels_archive) if labels_archive else None,
            "image_archive": str(image_archive) if image_archive else None,
            "expected_config": f"configs/datasets/motchallenge/{args.sequence.lower().replace('-', '_')}.yaml",
            "notes": [
                "Use MOT17-04 for surveillance/security Phase 1.3 validation.",
                "MOT17DetLabels.zip alone is not enough for ROI validation; frame images require MOT17Det.zip.",
                "The extractor only expands the selected sequence prefix to avoid unpacking the whole archive.",
            ],
        },
    )


if __name__ == "__main__":
    main()
