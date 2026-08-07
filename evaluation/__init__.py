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
from evaluation.roi_proposal_report import (
    RoiProposalInputs,
    RoiProposalReport,
    build_roi_proposal_report,
    write_roi_proposal_report_json,
    write_roi_proposal_report_markdown,
)

__all__ = [
    "ComparisonInputs",
    "ComparisonReport",
    "AnnotationQuality",
    "GtReport",
    "GtReportInputs",
    "RoiProposalInputs",
    "RoiProposalReport",
    "build_gt_report",
    "build_comparison_report",
    "build_roi_proposal_report",
    "collect_hardware_snapshot",
    "read_detection_jsonl",
    "write_gt_report_json",
    "write_gt_report_markdown",
    "write_report_json",
    "write_report_markdown",
    "write_roi_proposal_report_json",
    "write_roi_proposal_report_markdown",
]
