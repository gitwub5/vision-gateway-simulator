"""Summarize compatible ROI proposal validation runs."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.io import read_json, write_json, write_text
from visualization.artifacts import (
    artifact_path,
    ensure_compatible_runs,
    load_run_spec,
)


@dataclass(frozen=True)
class RunSummary:
    label: str
    run_root: str
    run_id: str
    diagnostics_level: str
    feedback_mode: str
    containment: float
    missed_gt: int
    small_containment: float
    missed_small_gt: int
    roi_per_frame: float
    selected_tile_per_frame: float
    tensor_cost_per_frame: float
    effective_reduction: float
    fallback_frames: int
    false_roi_rate: float
    tile_metrics_available: bool


def summarize_runs(run_specs: list[str]) -> dict[str, Any]:
    if not run_specs:
        raise ValueError("At least one run is required.")
    runs = [load_run_spec(spec) for spec in run_specs]
    compatibility = ensure_compatible_runs(runs)
    summaries = [
        build_run_summary(
            run.label,
            run.manifest,
            read_json(
                artifact_path(
                    run.root,
                    run.manifest.get("outputs", {}),
                    "report_json",
                    "reports/roi_proposal_report.json",
                )
            ),
            run.root,
        )
        for run in runs
    ]
    return {
        "schema_version": 1,
        "pipeline_type": "roi_proposal_run_summary",
        "compatibility": compatibility,
        "runs": [asdict(summary) for summary in summaries],
    }


def build_run_summary(
    label: str,
    manifest: dict[str, Any],
    report: dict[str, Any],
    root: Path,
) -> RunSummary:
    if report.get("schema_version") != 1:
        raise ValueError(f"Run {label} has unsupported ROI proposal report schema.")
    inputs = manifest.get("inputs", {})
    small = report.get("object_size_buckets", {}).get("small", {})
    return RunSummary(
        label=label,
        run_root=str(root),
        run_id=str(manifest.get("run_id", root.name)),
        diagnostics_level=str(inputs.get("diagnostics_level", "unknown")),
        feedback_mode=str(
            inputs.get("reference_feedback_mode")
            or _legacy_feedback_mode(inputs.get("reference_feedback_source"))
        ),
        containment=float(report.get("target_gt_roi_containment", 0.0)),
        missed_gt=int(report.get("missed_gt_count", 0)),
        small_containment=float(small.get("containment", 0.0)),
        missed_small_gt=int(small.get("missed_gt_count", 0)),
        roi_per_frame=float(report.get("average_roi_count_per_frame", 0.0)),
        selected_tile_per_frame=float(report.get("average_selected_tile_count_per_frame", 0.0)),
        tensor_cost_per_frame=float(report.get("average_tensor_batch_cost_per_frame", 0.0)),
        effective_reduction=float(report.get("effective_input_area_reduction", 0.0)),
        fallback_frames=int(report.get("fallback_frame_count", 0)),
        false_roi_rate=float(report.get("false_roi_rate", 0.0)),
        tile_metrics_available=bool(report.get("tile_metrics_available", False)),
    )


def render_markdown(summary: dict[str, Any]) -> str:
    compatibility = summary["compatibility"]
    lines = [
        "# ROI Proposal Run Comparison",
        "",
        "## Scope",
        "",
        f"- Input: `{compatibility['input_path']}`",
        f"- Camera: `{compatibility['camera_id']}`",
        f"- Frames: `{compatibility['start_frame']}` + `{compatibility['effective_frame_limit']}`",
        f"- Target classes: `{', '.join(compatibility['target_classes'])}`",
        "",
        "## Results",
        "",
        "| Run | Diagnostics | Feedback | Contain | Missed GT | Small contain | Missed small | ROI/frame | Tile/frame | Tensor/frame | Reduction | Fallback | False ROI | Tile metrics |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for run in summary["runs"]:
        lines.append(
            "| {label} | {diagnostics_level} | {feedback_mode} | {containment:.3f} | "
            "{missed_gt} | {small_containment:.3f} | {missed_small_gt} | "
            "{roi_per_frame:.3f} | {selected_tile_per_frame:.3f} | "
            "{tensor_cost_per_frame:.1f} | {effective_reduction:.3f} | "
            "{fallback_frames} | {false_roi_rate:.3f} | {tile_metrics_available} |".format(**run)
        )
    lines.append("")
    return "\n".join(lines)


def _legacy_feedback_mode(source: Any) -> str:
    return {
        "none": "none",
        "ground_truth": "oracle_gt",
        "full_frame_yolo": "actual_yolo",
    }.get(str(source), "unknown")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize compatible ROI proposal validation runs.")
    parser.add_argument("--run", action="append", required=True, help="Run spec in label=path form.")
    parser.add_argument("--output-markdown", required=True)
    parser.add_argument("--output-json", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = summarize_runs(args.run)
    write_json(summary, args.output_json)
    write_text(render_markdown(summary), args.output_markdown)
    print(json.dumps({"runs": len(summary["runs"]), "output_json": args.output_json}, indent=2))


if __name__ == "__main__":
    main()
