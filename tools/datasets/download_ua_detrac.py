"""Prepare UA-DETRAC archives supplied from the official dataset mirror."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.datasets.download_common import download_url, extract_zip, write_manifest


DEFAULT_OUTPUT_ROOT = Path("data/ua_detrac")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download or unpack UA-DETRAC archives.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--images-url", default=None, help="Direct URL for the DETRAC image archive.")
    parser.add_argument("--annotations-url", default=None, help="Direct URL for the DETRAC XML annotation archive.")
    parser.add_argument("--images-archive", type=Path, default=None, help="Already downloaded image archive.")
    parser.add_argument("--annotations-archive", type=Path, default=None, help="Already downloaded annotation archive.")
    parser.add_argument("--sequence", default="MVI_39361")
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive_dir = args.output_root / "archives"
    images_archive = args.images_archive
    annotations_archive = args.annotations_archive
    if args.images_url:
        images_archive = download_url(args.images_url, archive_dir / Path(args.images_url).name, force=args.force)
    if args.annotations_url:
        annotations_archive = download_url(
            args.annotations_url,
            archive_dir / Path(args.annotations_url).name,
            force=args.force,
        )
    if images_archive is None or annotations_archive is None:
        print(
            "UA-DETRAC does not currently have a repo-pinned stable direct URL here. "
            "Download the official image and XML annotation archives manually, then pass "
            "--images-archive and --annotations-archive, or pass direct mirror URLs."
        )
    if args.extract:
        if images_archive is None or annotations_archive is None:
            raise SystemExit("--extract requires both image and annotation archives.")
        extract_zip(images_archive, args.output_root, force=args.force)
        extract_zip(annotations_archive, args.output_root, force=args.force)
    write_manifest(
        args.output_root / "phase1_3_ua_detrac_manifest.json",
        {
            "dataset": "UA-DETRAC",
            "selected_sequence": args.sequence,
            "images_archive": str(images_archive) if images_archive else None,
            "annotations_archive": str(annotations_archive) if annotations_archive else None,
            "expected_config": f"configs/datasets/ua_detrac/ua_detrac_{args.sequence.lower()}.yaml",
            "phase1_3_role": "traffic/parking validation",
        },
    )


if __name__ == "__main__":
    main()
