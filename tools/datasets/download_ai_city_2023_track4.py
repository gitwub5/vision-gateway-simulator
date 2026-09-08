"""Download AI City Challenge 2023 Track 4 data for retail validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.datasets.download_common import download_google_drive_file, extract_zip, write_manifest


FILE_ID = "1mlMnkJ0mBQD0vm6vbLc_zojFTYLNUXB8"
DEFAULT_OUTPUT_ROOT = Path("data/ai_city_2023_track4")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download AICity 2023 Track 4 archive.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--accept-license",
        action="store_true",
        help="Required because the upstream download page states that clicking the link accepts the data license.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.accept_license:
        raise SystemExit(
            "AICity Track 4 requires accepting the upstream data license. "
            "Review https://www.aicitychallenge.org/2023-track4-download/ and re-run with --accept-license."
        )
    archive_path = args.output_root / "archives" / "AICity23_Track4_Automated_Checkout.zip"
    download_google_drive_file(FILE_ID, archive_path, force=args.force)
    if args.extract:
        extract_zip(archive_path, args.output_root, force=args.force)
    write_manifest(
        args.output_root / "phase1_3_ai_city_2023_track4_manifest.json",
        {
            "dataset": "AI City Challenge 2023 Track 4",
            "source": "https://www.aicitychallenge.org/2023-track4-download/",
            "google_drive_file_id": FILE_ID,
            "archive": str(archive_path),
            "expected_config": "configs/datasets/ai_city/ai_city_2023_track4.yaml",
            "phase1_3_role": "retail/space analytics validation",
        },
    )


if __name__ == "__main__":
    main()
