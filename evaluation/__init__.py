"""Evaluation metric helpers."""

from evaluation.reports.comparison import (
    ComparisonInputs,
    ComparisonReport,
    build_comparison_report,
    read_detection_jsonl,
    write_report_json,
    write_report_markdown,
)
from evaluation.reports.gt import (
    AnnotationQuality,
    GtReport,
    GtReportInputs,
    build_gt_report,
    write_gt_report_json,
    write_gt_report_markdown,
)
from evaluation.system.hardware import collect_hardware_snapshot
from evaluation.reports.roi_proposal import (
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
