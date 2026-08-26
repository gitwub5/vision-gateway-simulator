"""Render review views for one saved ROI proposal run."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_loader import create_dataset_stream, load_dataset_config
from visualization.artifacts import load_roi_run
from visualization.roi_proposal_renderer import REVIEW_VIEWS, render_roi_run_review


def main() -> None:
    args = parse_args()
    run = load_roi_run(args.run_root)
    compatibility = run.compatibility_key
    dataset_config = load_dataset_config(run.dataset_config_path)
    dataset_config = replace(
        dataset_config,
        start_frame=int(compatibility["start_frame"]),
        frame_limit=int(compatibility["effective_frame_limit"]),
    )
    views = REVIEW_VIEWS if args.view == "all" else (args.view,)
    explicit = [
        (str(compatibility["camera_id"]), frame_id)
        for frame_id in args.frame
    ]
    output_root = Path(args.output_root) if args.output_root else Path(args.run_root) / "visualizations" / "review"
    summary = render_roi_run_review(
        run=run,
        frames=create_dataset_stream(dataset_config),
        output_root=output_root,
        views=views,
        selection_preset="explicit" if explicit else args.preset,
        max_frames=args.max_frames,
        explicit_frames=explicit,
    )
    print(json.dumps(summary.to_json_dict(), indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render one saved ROI proposal run.")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--view", choices=(*REVIEW_VIEWS, "all"), default="all")
    parser.add_argument("--preset", choices=["missed", "cost"], default="missed")
    parser.add_argument("--frame", action="append", type=int, default=[])
    parser.add_argument("--max-frames", type=int, default=80)
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    main()
