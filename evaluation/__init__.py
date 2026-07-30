"""Evaluation metric helpers."""

from evaluation.comparison_report import (
    ComparisonInputs,
    ComparisonReport,
    build_comparison_report,
    read_detection_jsonl,
    write_report_json,
    write_report_markdown,
)
from evaluation.gt_report import (
    AnnotationQuality,
    GtReport,
    GtReportInputs,
    build_gt_report,
    write_gt_report_json,
    write_gt_report_markdown,
)
from evaluation.hardware_metrics import collect_hardware_snapshot

__all__ = [
    "ComparisonInputs",
    "ComparisonReport",
    "AnnotationQuality",
    "GtReport",
    "GtReportInputs",
    "build_gt_report",
    "build_comparison_report",
    "collect_hardware_snapshot",
    "read_detection_jsonl",
    "write_gt_report_json",
    "write_gt_report_markdown",
    "write_report_json",
    "write_report_markdown",
]
