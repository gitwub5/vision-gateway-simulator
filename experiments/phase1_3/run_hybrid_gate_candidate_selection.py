"""Run Phase 1.3-G hybrid gate candidate selection."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.io import write_json
from evaluation.reports.hybrid_gate_selection import (
    build_hybrid_gate_selection_report,
    write_hybrid_gate_selection_report_json,
    write_hybrid_gate_selection_report_markdown,
)

DEFAULT_OUTPUT_ROOT = "outputs/hybrid_gate_selection"
DEFAULT_STATIC_SUMMARY = "outputs/static_zone_prior_matrices/phase1_3_static_zone_prior_20260916_155527/summary.json"
DEFAULT_TRACKER_SUMMARY = "outputs/tracker_memory_matrices/phase1_3_tracker_memory_20260917_103714/summary.json"
DEFAULT_LIGHTWEIGHT_SUMMARY = (
    "outputs/lightweight_visual_signal_matrices/phase1_3_lightweight_visual_signal_20260917_104336/summary.json"
)
DEFAULT_TEMPORAL_SUMMARY = "outputs/temporal_gate_matrices/phase1_3_temporal_gate_20260916_152806/summary.json"
DEFAULT_COMPRESSION_SUMMARY = "outputs/compression_signal_matrices/phase1_3_compression_signal_20260917_105124/summary.json"


def run_hybrid_gate_candidate_selection(
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    run_id: str | None = None,
    static_summary: str | Path = DEFAULT_STATIC_SUMMARY,
    tracker_summary: str | Path = DEFAULT_TRACKER_SUMMARY,
    lightweight_summary: str | Path = DEFAULT_LIGHTWEIGHT_SUMMARY,
    temporal_summary: str | Path = DEFAULT_TEMPORAL_SUMMARY,
    compression_summary: str | Path | None = DEFAULT_COMPRESSION_SUMMARY,
) -> dict[str, object]:
    suffix = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    selected_run_id = run_id or f"phase1_3_hybrid_gate_candidate_selection_{suffix}"
    run_root = Path(output_root) / selected_run_id
    report_root = run_root / "reports"
    report = build_hybrid_gate_selection_report(
        static_summary_path=static_summary,
        tracker_summary_path=tracker_summary,
        lightweight_summary_path=lightweight_summary,
        temporal_summary_path=temporal_summary,
        compression_summary_path=compression_summary,
    )
    report_json_path = report_root / "hybrid_gate_selection_report.json"
    report_md_path = report_root / "hybrid_gate_selection_report.md"
    write_hybrid_gate_selection_report_json(report, report_json_path)
    write_hybrid_gate_selection_report_markdown(report, report_md_path)
    manifest = {
        "schema_version": 1,
        "pipeline_type": "hybrid_gate_candidate_selection",
        "run_id": selected_run_id,
        "outputs": {
            "report_json": str(report_json_path),
            "report_markdown": str(report_md_path),
        },
        "summary": report.to_json_dict(),
    }
    write_json(manifest, run_root / "manifest.json")
    return {"run_root": str(run_root), **manifest}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1.3-G hybrid gate candidate selection.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id")
    parser.add_argument("--static-summary", default=DEFAULT_STATIC_SUMMARY)
    parser.add_argument("--tracker-summary", default=DEFAULT_TRACKER_SUMMARY)
    parser.add_argument("--lightweight-summary", default=DEFAULT_LIGHTWEIGHT_SUMMARY)
    parser.add_argument("--temporal-summary", default=DEFAULT_TEMPORAL_SUMMARY)
    parser.add_argument("--compression-summary", default=DEFAULT_COMPRESSION_SUMMARY)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run_hybrid_gate_candidate_selection(
        output_root=args.output_root,
        run_id=args.run_id,
        static_summary=args.static_summary,
        tracker_summary=args.tracker_summary,
        lightweight_summary=args.lightweight_summary,
        temporal_summary=args.temporal_summary,
        compression_summary=args.compression_summary,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
