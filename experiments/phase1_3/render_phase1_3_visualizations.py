"""Render review visualizations for Phase 1.3 ROI Gate POC results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from visualization.phase1_3_renderer import DEFAULT_RUNS, render_phase1_3_visualizations


def main() -> None:
    args = parse_args()
    summary = render_phase1_3_visualizations(
        run_roots=args.run_root or list(DEFAULT_RUNS),
        output_root=args.output_root,
        max_frames_per_run=args.max_frames_per_run,
    )
    print(json.dumps(summary.to_json_dict(), indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Phase 1.3 result review visualizations.")
    parser.add_argument(
        "--run-root",
        action="append",
        help="Run root containing manifest.json. Can be passed multiple times. Defaults to final Phase 1.3 runs.",
    )
    parser.add_argument("--output-root", default="outputs/visualizations/phase1_3")
    parser.add_argument("--max-frames-per-run", type=int, default=6)
    return parser.parse_args()


if __name__ == "__main__":
    main()
