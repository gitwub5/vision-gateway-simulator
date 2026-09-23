"""Run Phase 1.3-F compressed-domain signal prototype on one dataset."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.io import load_yaml_config, write_json, write_jsonl
from data_loader.dataset_stream import load_dataset_config
from evaluation.reports.compression_signal import (
    CompressionFrameRecord,
    build_compression_signal_report,
    unavailable_compression_signal_report,
    write_compression_signal_report_json,
    write_compression_signal_report_markdown,
)

DEFAULT_OUTPUT_ROOT = "outputs/compression_signal_poc"


def run_compression_signal_poc(
    dataset_config_path: str | Path,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    experiment_name: str | None = None,
    run_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    dataset_path = resolve_project_path(dataset_config_path)
    raw_config = load_yaml_config(dataset_path)
    dataset_config = load_dataset_config(dataset_path)
    if limit is not None:
        dataset_config = replace(dataset_config, frame_limit=limit)

    name = experiment_name or str(raw_config.get("name") or dataset_path.stem)
    suffix = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    selected_run_id = run_id or f"{name}_compression_signal_{suffix}"
    run_root = Path(output_root) / selected_run_id
    report_root = run_root / "reports"
    frame_records_path = run_root / "compression_frame_records.jsonl"
    report_json_path = report_root / "compression_signal_report.json"
    report_md_path = report_root / "compression_signal_report.md"
    input_path = resolve_project_path(dataset_config.input_path)

    records: list[CompressionFrameRecord] = []
    if dataset_config.type != "video":
        report = unavailable_compression_signal_report(
            dataset_config=project_relative(dataset_path),
            experiment_name=name,
            dataset_type=dataset_config.type,
            input_path=project_relative(input_path),
            reason="dataset is an image sequence; encoded stream metadata is not preserved",
        )
    elif not input_path.is_file():
        report = unavailable_compression_signal_report(
            dataset_config=project_relative(dataset_path),
            experiment_name=name,
            dataset_type=dataset_config.type,
            input_path=project_relative(input_path),
            reason="video input path does not exist",
        )
    elif shutil.which("ffprobe") is None:
        report = unavailable_compression_signal_report(
            dataset_config=project_relative(dataset_path),
            experiment_name=name,
            dataset_type=dataset_config.type,
            input_path=project_relative(input_path),
            reason="ffprobe is not installed; cannot inspect encoded frame metadata locally",
        )
    else:
        records = _extract_ffprobe_frame_records(input_path, dataset_config.frame_limit)
        report = build_compression_signal_report(
            records=records,
            dataset_config=project_relative(dataset_path),
            experiment_name=name,
            dataset_type=dataset_config.type,
            input_path=project_relative(input_path),
        )

    write_jsonl(records, frame_records_path)
    write_compression_signal_report_json(report, report_json_path)
    write_compression_signal_report_markdown(report, report_md_path)
    manifest = {
        "schema_version": 1,
        "pipeline_type": "compression_signal_poc",
        "experiment_name": name,
        "run_id": selected_run_id,
        "dataset_config": project_relative(dataset_path),
        "limit": limit,
        "dataset_type": dataset_config.type,
        "input_path": project_relative(input_path),
        "outputs": {
            "frame_records": str(frame_records_path),
            "report_json": str(report_json_path),
            "report_markdown": str(report_md_path),
        },
        "summary": report.to_json_dict(),
    }
    write_json(manifest, run_root / "manifest.json")
    return {"run_root": str(run_root), **manifest}


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def project_relative(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return str(candidate.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(candidate)


def _extract_ffprobe_frame_records(input_path: Path, limit: int | None) -> list[CompressionFrameRecord]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_frames",
        "-show_entries",
        "frame=best_effort_timestamp_time,pict_type,key_frame,pkt_size",
        "-of",
        "json",
        str(input_path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    records: list[CompressionFrameRecord] = []
    for frame_index, frame in enumerate(data.get("frames", [])):
        if limit is not None and frame_index >= limit:
            break
        records.append(
            CompressionFrameRecord(
                frame_index=frame_index,
                timestamp=_optional_float(frame.get("best_effort_timestamp_time")),
                pict_type=str(frame.get("pict_type") or "unknown"),
                key_frame=str(frame.get("key_frame", "0")) == "1",
                packet_size=_optional_int(frame.get("pkt_size")),
            )
        )
    return records


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1.3-F compression signal prototype.")
    parser.add_argument("--dataset-config", required=True)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--experiment-name")
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run_compression_signal_poc(
        dataset_config_path=args.dataset_config,
        output_root=args.output_root,
        experiment_name=args.experiment_name,
        run_id=args.run_id,
        limit=args.limit,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
