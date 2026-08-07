"""Download one NVIDIA PhysicalAI Smart Spaces row video and its GT JSON.

The full dataset is too large for local validation. This helper resolves a
Hugging Face dataset viewer row id to the underlying repository video path,
derives the scene-level ground_truth.json path, and downloads only those files.
"""

from __future__ import annotations

import argparse
import json
import shutil
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_DATASET = "nvidia/PhysicalAI-SmartSpaces"
DEFAULT_CONFIG = "default"
DEFAULT_SPLIT = "train"
DEFAULT_OUTPUT_ROOT = Path("data/physicalai_smartspaces")


def main() -> None:
    args = parse_args()
    row = resolve_row(args)
    selection = resolve_selection(row, args)
    output_dir = args.output_root / f"row_{args.row_id:04d}"
    video_local_path = output_dir / selection.video_repo_path
    gt_local_path = output_dir / selection.ground_truth_repo_path
    config_path = args.config_output or Path(f"configs/dataset.physicalai_row{args.row_id:04d}.yaml")

    print(
        json.dumps(
            {
                "row_id": args.row_id,
                "dataset": args.dataset,
                "split": args.split,
                "video_repo_path": selection.video_repo_path,
                "ground_truth_repo_path": selection.ground_truth_repo_path,
                "camera_id": selection.camera_id,
                "output_dir": str(output_dir),
                "dataset_config": str(config_path),
            },
            indent=2,
        )
    )

    if args.dry_run:
        return

    download_files(
        dataset=args.dataset,
        repo_paths=[selection.video_repo_path, selection.ground_truth_repo_path],
        output_dir=output_dir,
    )
    write_dataset_config(
        config_path=config_path,
        video_path=video_local_path,
        gt_path=gt_local_path,
        camera_id=selection.camera_id,
        frame_limit=args.frame_limit,
        fps_override=args.fps_override,
    )
    print(f"Wrote dataset config: {config_path}")


class PhysicalAiSelection:
    def __init__(self, video_repo_path: str, ground_truth_repo_path: str, camera_id: str) -> None:
        self.video_repo_path = video_repo_path
        self.ground_truth_repo_path = ground_truth_repo_path
        self.camera_id = camera_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download one PhysicalAI row video and scene GT.")
    parser.add_argument("--row-id", type=int, required=True, help="Hugging Face dataset viewer row offset.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--config-output", type=Path, default=None)
    parser.add_argument("--frame-limit", type=int, default=120)
    parser.add_argument("--fps-override", type=float, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Resolve paths without downloading files.")
    return parser.parse_args()


def resolve_row(args: argparse.Namespace) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "dataset": args.dataset,
            "config": args.config,
            "split": args.split,
            "offset": args.row_id,
            "length": 1,
        }
    )
    url = f"https://datasets-server.huggingface.co/rows?{query}"
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            "Could not resolve the Hugging Face dataset row. "
            "Check network access, dataset permissions, and row id."
        ) from exc

    rows = payload.get("rows", [])
    if not rows:
        raise RuntimeError(f"No row found for offset {args.row_id}")
    return dict(rows[0].get("row") or {})


def resolve_selection(row: dict[str, Any], args: argparse.Namespace) -> PhysicalAiSelection:
    video_repo_path = find_video_repo_path(row)
    scene_path, camera_id = split_scene_and_camera(video_repo_path)
    return PhysicalAiSelection(
        video_repo_path=video_repo_path,
        ground_truth_repo_path=f"{scene_path}/ground_truth.json",
        camera_id=camera_id,
    )


def download_files(dataset: str, repo_paths: list[str], output_dir: Path) -> None:
    hf_cli = shutil.which("hf")
    if hf_cli:
        command = [
            hf_cli,
            "download",
            dataset,
            "--repo-type",
            "dataset",
            *repo_paths,
            "--local-dir",
            str(output_dir),
        ]
        subprocess.run(command, check=True)
        return

    print("`hf` CLI not found; falling back to direct Hugging Face resolve URLs.")
    for repo_path in repo_paths:
        target = output_dir / repo_path
        target.parent.mkdir(parents=True, exist_ok=True)
        url = make_huggingface_resolve_url(dataset, repo_path)
        print(f"Downloading {url}")
        print(f"→ {target}")
        urllib.request.urlretrieve(url, target)


def make_huggingface_resolve_url(dataset: str, repo_path: str) -> str:
    encoded_path = "/".join(urllib.parse.quote(part) for part in repo_path.split("/"))
    return f"https://huggingface.co/datasets/{dataset}/resolve/main/{encoded_path}"


def find_video_repo_path(row: dict[str, Any]) -> str:
    for value in walk_values(row):
        if not isinstance(value, str) or ".mp4" not in value:
            continue
        match = re.search(
            r"(MTMC_Tracking_\d{4}/(?:train|val|test|eval)/[^?#\"']+/videos/Camera_\d+\.mp4)",
            value,
        )
        if match:
            return match.group(1)
        if value.startswith("MTMC_Tracking_") and value.endswith(".mp4"):
            return value
    raise RuntimeError(f"Could not find a PhysicalAI video path in row payload: {row}")


def split_scene_and_camera(video_repo_path: str) -> tuple[str, str]:
    match = re.match(r"(.+)/videos/(Camera_\d+)\.mp4$", video_repo_path)
    if not match:
        raise RuntimeError(f"Could not derive scene/camera from video path: {video_repo_path}")
    return match.group(1), match.group(2)


def walk_values(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_values(item)
    else:
        yield value


def write_dataset_config(
    config_path: Path,
    video_path: Path,
    gt_path: Path,
    camera_id: str,
    frame_limit: int,
    fps_override: float | None,
) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    fps_value = "null" if fps_override is None else str(fps_override)
    config_path.write_text(
        "\n".join(
            [
                "dataset:",
                "  type: video",
                f"  input_path: {video_path}",
                f"  camera_id: {camera_id}",
                f"  fps_override: {fps_value}",
                f"  frame_limit: {frame_limit}",
                "  start_frame: 0",
                "",
                "annotations:",
                "  enabled: true",
                "  type: physicalai_smartspaces_json",
                f"  input_path: {gt_path}",
                f"  camera_id: {camera_id}",
                "  bbox_format: xyxy",
                "  quality:",
                "    completeness: synthetic_exhaustive",
                "    expected_exhaustive: true",
                "    unreliable_metrics: []",
                "    notes:",
                "      - PhysicalAI Smart Spaces is synthetic multi-camera scene-level GT.",
                "      - The loader filters ground_truth.json to the selected camera_id.",
                "      - Verify bbox_format against the downloaded ground_truth.json before using hard metrics.",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    if __package__ is None or __package__ == "":
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()
