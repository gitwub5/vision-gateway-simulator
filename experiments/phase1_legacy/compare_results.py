"""Compare full-frame and ROI-gated experiment outputs."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation import (
    ComparisonInputs,
    build_comparison_report,
    write_report_json,
    write_report_markdown,
)


def main() -> None:
    args = _parse_args()
    inputs = ComparisonInputs(
        full_frame_detections=Path(args.full_frame_detections),
        roi_detections=Path(args.roi_detections),
        full_frame_metrics=Path(args.full_frame_metrics),
        roi_metrics=Path(args.roi_metrics),
        roi_metadata=Path(args.roi_metadata),
        frame_metadata=Path(args.frame_metadata),
        report_json=Path(args.report_json),
        report_markdown=Path(args.report_markdown),
    )

    report = build_comparison_report(inputs, iou_threshold=args.iou_threshold)
    write_report_json(report, inputs.report_json)
    write_report_markdown(report, inputs.report_markdown)

    print(f"Wrote comparison report JSON to {inputs.report_json}")
    print(f"Wrote comparison report Markdown to {inputs.report_markdown}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare full-frame and ROI-gated outputs.")
    parser.add_argument("--full-frame-detections", default="outputs/detections/full_frame.jsonl")
    parser.add_argument("--roi-detections", default="outputs/detections/roi_yolo.jsonl")
    parser.add_argument("--full-frame-metrics", default="outputs/reports/full_frame_metrics.json")
    parser.add_argument("--roi-metrics", default="outputs/reports/roi_yolo_metrics.json")
    parser.add_argument("--roi-metadata", default="outputs/roi_metadata/rule_roi.jsonl")
    parser.add_argument("--frame-metadata", default="outputs/roi_metadata/gate_decisions.jsonl")
    parser.add_argument("--report-json", default="outputs/reports/comparison_report.json")
    parser.add_argument("--report-markdown", default="outputs/reports/comparison_report.md")
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    return parser.parse_args()


if __name__ == "__main__":
    main()
