"""Render compatible ROI proposal runs side by side."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.io import write_json, write_text
from tools.reports.summarize_roi_proposal_runs import render_markdown, summarize_runs
from visualization.roi_policy_comparison_renderer import render_roi_policy_comparison


def main() -> None:
    args = parse_args()
    summary = render_roi_policy_comparison(
        dataset_config_path=None,
        output_dir=args.output_root,
        run_specs=args.run,
        selection_preset=args.preset,
        explicit_frame_ids=args.frame,
        max_frames=args.max_frames,
        panel_width=args.panel_width,
    )
    metric_summary = summarize_runs(args.run)
    output_root = Path(args.output_root)
    write_text(render_markdown(metric_summary), output_root / "summary.md")
    write_json(metric_summary, output_root / "summary.json")
    print(json.dumps(summary, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare compatible ROI proposal runs.")
    parser.add_argument("--run", action="append", required=True, help="Run spec in label=path form.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--preset", choices=["disagreement", "missed", "cost"], default="disagreement")
    parser.add_argument("--frame", action="append", type=int, default=[])
    parser.add_argument("--max-frames", type=int, default=80)
    parser.add_argument("--panel-width", type=int, default=960)
    return parser.parse_args()


if __name__ == "__main__":
    main()
