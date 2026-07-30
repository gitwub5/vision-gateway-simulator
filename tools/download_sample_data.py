"""Download or describe sample data used by local validation.

Only public, redistribution-safe samples are downloaded automatically. Datasets
with usage agreements or internal access requirements are described but not
downloaded by this script.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@dataclass(frozen=True)
class SampleDataset:
    key: str
    description: str
    output_path: Path
    config_path: Path
    url: str | None
    expected_size_bytes: int | None
    usage_note: str
    auto_download: bool = True


SAMPLES: dict[str, SampleDataset] = {
    "opencv-vtest": SampleDataset(
        key="opencv-vtest",
        description="OpenCV fixed-camera pedestrian sample video.",
        output_path=Path("data/opencv_vtest/vtest.avi"),
        config_path=Path("configs/dataset.opencv_vtest.yaml"),
        url="https://raw.githubusercontent.com/opencv/opencv/master/samples/data/vtest.avi",
        expected_size_bytes=None,
        usage_note=(
            "OpenCV vtest.avi is a small fixed-camera pedestrian sample. Use it for "
            "local Phase 1 pipeline validation before preparing Construction Site "
            "Static Camera, OD-VIRAT, or internal CCTV data."
        ),
    ),
    "construction-site-static-camera": SampleDataset(
        key="construction-site-static-camera",
        description="Construction-site images captured from four static cameras.",
        output_path=Path("data/construction_site_static_camera/"),
        config_path=Path("configs/dataset.construction_site_static_camera.yaml"),
        url=None,
        expected_size_bytes=None,
        usage_note=(
            "Preferred public Phase 1.1 validation candidate for industrial fixed-camera "
            "monitoring. The dataset contains construction-site images from static cameras "
            "with object coordinate txt files for classes such as Person, Dump_truck, "
            "Excavator, Truck, and crane/truck variants. Download it manually from "
            "https://doi.org/10.26439/ulima.datasets.13359 after checking terms, then "
            "place images under data/construction_site_static_camera/images and labels "
            "under data/construction_site_static_camera/labels. Keep annotations disabled "
            "until the source txt format is confirmed and a converter is added."
        ),
        auto_download=False,
    ),
    "od-virat-tiny": SampleDataset(
        key="od-virat-tiny",
        description="OD-VIRAT Tiny or a small OD-VIRAT subset.",
        output_path=Path("data/od_virat_tiny/"),
        config_path=Path("configs/dataset.od_virat_tiny.yaml"),
        url=None,
        expected_size_bytes=None,
        usage_note=(
            "Use this for GT-based Phase 1/1.1 validation when available. OD-VIRAT Tiny is "
            "provided through the OD-VIRAT project as a Google Drive folder rather than "
            "as a stable direct-download single file in this repo. Check the official "
            "dataset page https://iscaaslab.com/datasets/, OD-VIRAT DATA.md "
            "https://github.com/hayatkhan8660-maker/OD-VIRAT/blob/main/DATA.md, and "
            "the Tiny folder "
            "https://drive.google.com/drive/folders/1MqVKIfS_RimUVVin1UHk_uwPmex5vid7?usp=drive_link. "
            "Download the Tiny zip files from Google Drive and extract them as-is under "
            "data/od_virat_tiny/. Keep the upstream folder names. The default validation "
            "config points at data/od_virat_tiny/data/test and "
            "data/od_virat_tiny/json_anntations/test_annotations.json. After the "
            "annotation format is confirmed, implement the dataset-specific annotation "
            "loader."
        ),
        auto_download=False,
    ),
    "internal-cctv": SampleDataset(
        key="internal-cctv",
        description="Internal fixed-camera CCTV sample.",
        output_path=Path("data/internal_cctv/"),
        config_path=Path("configs/dataset.internal_cctv_sample.yaml"),
        url=None,
        expected_size_bytes=None,
        usage_note=(
            "Preferred for company-specific smoke/validation once an internal sample is available. "
            "Do not commit raw video; place it under data/ and create a local dataset config."
        ),
        auto_download=False,
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download or describe sample validation data.")
    parser.add_argument("--list", action="store_true", help="List known sample datasets.")
    parser.add_argument("--dataset", choices=sorted(SAMPLES), help="Dataset key to download or describe.")
    parser.add_argument("--force", action="store_true", help="Re-download even if the target file exists.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.list or not args.dataset:
        print_samples()
        return

    sample = SAMPLES[args.dataset]
    print_sample(sample)
    if not sample.auto_download:
        print("\nAutomatic download is disabled for this dataset. Follow the usage note above.")
        return

    download_sample(sample, force=args.force)
    print_next_steps(sample)


def print_samples() -> None:
    print("Available sample datasets:")
    for sample in SAMPLES.values():
        mode = "download" if sample.auto_download else "manual"
        print(f"- {sample.key} ({mode}): {sample.description}")


def print_sample(sample: SampleDataset) -> None:
    print(
        {
            "dataset": sample.key,
            "description": sample.description,
            "output_path": str(sample.output_path),
            "config_path": str(sample.config_path),
            "auto_download": sample.auto_download,
        }
    )
    print(sample.usage_note)


def download_sample(sample: SampleDataset, force: bool = False) -> None:
    if sample.url is None:
        raise ValueError(f"No download URL configured for {sample.key}")

    sample.output_path.parent.mkdir(parents=True, exist_ok=True)
    if sample.output_path.exists() and not force:
        print(f"Already exists, skipping download: {sample.output_path}")
        _validate_size(sample)
        return

    print(f"Downloading {sample.url}")
    print(f"→ {sample.output_path}")
    urllib.request.urlretrieve(sample.url, sample.output_path)
    _validate_size(sample)


def _validate_size(sample: SampleDataset) -> None:
    if not sample.output_path.exists():
        raise FileNotFoundError(sample.output_path)
    actual_size = sample.output_path.stat().st_size
    if sample.expected_size_bytes is not None and actual_size != sample.expected_size_bytes:
        raise RuntimeError(
            f"Downloaded size mismatch for {sample.output_path}: "
            f"expected {sample.expected_size_bytes}, got {actual_size}"
        )
    print({"path": str(sample.output_path), "size_bytes": actual_size})


def print_next_steps(sample: SampleDataset) -> None:
    print("\nNext steps:")
    print(f"Use config: {sample.config_path}")
    print(
        "Inspect loader:\n"
        f"  python experiments/inspect_dataset_stream.py --config {sample.config_path} --limit 3"
    )
    print(
        "Run ROI metadata smoke test:\n"
        f"  python experiments/run_rule_roi_baseline.py --dataset-config {sample.config_path} "
        "--gate-config configs/npx_gate.yaml --limit 30"
    )


if __name__ == "__main__":
    main()
