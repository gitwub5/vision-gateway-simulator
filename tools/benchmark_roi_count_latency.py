#!/usr/bin/env python3
"""Build ROI-count bucket latency summaries from a Phase 1 run."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.phase1_summary import (
    roi_bucket_summaries_to_markdown,
    summarize_roi_count_latency,
    write_summary_json,
    write_text,
)


def main() -> None:
    args = parse_args()
    summaries = summarize_roi_count_latency(args.run_root, iou_threshold=args.iou_threshold)
    if args.output_json:
        write_summary_json(summaries, args.output_json)
    if args.output_markdown:
        write_text(roi_bucket_summaries_to_markdown(summaries), args.output_markdown)
    if not args.output_json and not args.output_markdown:
        print(roi_bucket_summaries_to_markdown(summaries))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize ROI-count latency buckets.")
    parser.add_argument("run_root", help="Experiment output root directory.")
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-markdown", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    main()
