"""Download VisDrone-VID archives for camera-motion stress validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.datasets.download_common import download_google_drive_file, extract_zip, write_manifest


SPLITS = {
    "train": {
        "file_id": "1NSNapZQHar22OYzQYuXCugA3QlMndzvw",
        "archive": "VisDrone2018-VID-train.zip",
        "size_note": "about 7.53 GB",
    },
    "val": {
        "file_id": "1xuG7Z3IhVfGGKMe3Yj6RnrFHqo_d2a1B",
        "archive": "VisDrone2018-VID-val.zip",
        "size_note": "about 1.49 GB",
    },
    "test-dev": {
        "file_id": "1-BEq--FcjshTF1UwUabby_LHhYj41os5",
        "archive": "VisDrone2018-VID-test-dev.zip",
        "size_note": "about 2.14 GB",
    },
}
DEFAULT_OUTPUT_ROOT = Path("data/visdrone_vid")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download VisDrone-VID split archives.")
    parser.add_argument("--split", choices=sorted(SPLITS), default="val")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    split = SPLITS[args.split]
    archive_path = args.output_root / "archives" / split["archive"]
    print(f"Selected VisDrone-VID {args.split} ({split['size_note']}).")
    download_google_drive_file(split["file_id"], archive_path, force=args.force)
    if args.extract:
        extract_zip(archive_path, args.output_root, force=args.force)
    write_manifest(
        args.output_root / f"phase1_3_visdrone_vid_{args.split}_manifest.json",
        {
            "dataset": "VisDrone-VID",
            "split": args.split,
            "source": "https://github.com/VisDrone/VisDrone-Dataset",
            "google_drive_file_id": split["file_id"],
            "archive": str(archive_path),
            "expected_config": f"configs/datasets/visdrone/visdrone_vid_{args.split}.yaml",
            "phase1_3_role": "camera-motion and small-object stress check",
        },
    )


if __name__ == "__main__":
    main()
