"""Target-aware ROI proposal validation metrics."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from common import GateFrameMetadata, GroundTruthAnnotation, ROIMetadata, TriggerType
from evaluation.class_filter import filter_gt_by_target_classes, normalize_target_classes
from evaluation.roi_containment import contains_bbox


@dataclass(frozen=True)
class RoiProposalInputs:
    ground_truth: Path
    roi_metadata: Path
    frame_metadata: Path
    report_json: Path
    report_markdown: Path

    def to_json_dict(self) -> dict[str, str]:
        return {
            "ground_truth": str(self.ground_truth),
            "roi_metadata": str(self.roi_metadata),
            "frame_metadata": str(self.frame_metadata),
            "report_json": str(self.report_json),
            "report_markdown": str(self.report_markdown),
        }


@dataclass(frozen=True)
class RoiProposalReport:
    inputs: RoiProposalInputs
    target_classes: tuple[str, ...]
    frame_count: int
    target_gt_count: int
    contained_gt_count: int
    target_gt_frame_count: int
    no_roi_target_frame_count: int
    missed_target_frame_count: int
    roi_record_count: int
    roi_frame_count: int
    false_roi_count: int
    full_frame_check_frame_count: int
    fallback_frame_count: int
    full_frame_input_pixel_area: int
    roi_only_input_pixel_area: int
    effective_input_pixel_area: int
    average_roi_count_per_frame: float
    average_total_roi_area_ratio_per_frame: float
    max_total_roi_area_ratio_per_frame: float
    gate_average_latency_ms: float
    gate_max_latency_ms: float

    @property
    def missed_gt_count(self) -> int:
        return self.target_gt_count - self.contained_gt_count

    @property
    def target_gt_roi_containment(self) -> float:
        if self.target_gt_count == 0:
            return 0.0
        return self.contained_gt_count / self.target_gt_count

    @property
    def false_roi_rate(self) -> float:
        if self.roi_record_count == 0:
            return 0.0
        return self.false_roi_count / self.roi_record_count

    @property
    def fallback_frame_rate(self) -> float:
        if self.frame_count == 0:
            return 0.0
        return self.fallback_frame_count / self.frame_count

    @property
    def full_frame_check_rate(self) -> float:
        if self.frame_count == 0:
            return 0.0
        return self.full_frame_check_frame_count / self.frame_count

    @property
    def roi_only_input_area_reduction(self) -> float:
        return _reduction_ratio(self.full_frame_input_pixel_area, self.roi_only_input_pixel_area)

    @property
    def effective_input_area_reduction(self) -> float:
        return _reduction_ratio(self.full_frame_input_pixel_area, self.effective_input_pixel_area)

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema_version"] = 1
        data["inputs"] = self.inputs.to_json_dict()
        data["target_classes"] = list(self.target_classes)
        data["missed_gt_count"] = self.missed_gt_count
        data["target_gt_roi_containment"] = self.target_gt_roi_containment
        data["false_roi_rate"] = self.false_roi_rate
        data["fallback_frame_rate"] = self.fallback_frame_rate
        data["full_frame_check_rate"] = self.full_frame_check_rate
        data["roi_only_input_area_reduction"] = self.roi_only_input_area_reduction
        data["effective_input_area_reduction"] = self.effective_input_area_reduction
        return data

    def to_markdown(self) -> str:
        lines = [
            "# ROI Proposal Validation Report",
            "",
            "## Target Scope",
            "",
            f"- Target classes: `{', '.join(self.target_classes) if self.target_classes else 'all'}`",
            "",
            "## Summary",
            "",
            f"- Target GT ROI containment: {_format_ratio(self.target_gt_roi_containment)}",
            f"- Missed target GT objects: {self.missed_gt_count}",
            f"- No-ROI target frames: {self.no_roi_target_frame_count}",
            f"- Missed target frames: {self.missed_target_frame_count}",
            f"- ROI-only input area reduction: {_format_ratio(self.roi_only_input_area_reduction)}",
            f"- Effective input area reduction including full-frame checks: {_format_ratio(self.effective_input_area_reduction)}",
            f"- Average ROI count per frame: {self.average_roi_count_per_frame:.3f}",
            f"- Average total ROI area ratio per frame: {_format_ratio(self.average_total_roi_area_ratio_per_frame)}",
            f"- Max total ROI area ratio per frame: {_format_ratio(self.max_total_roi_area_ratio_per_frame)}",
            f"- Full-frame check rate: {_format_ratio(self.full_frame_check_rate)}",
            f"- Fallback frame rate: {_format_ratio(self.fallback_frame_rate)}",
            f"- False ROI rate against target GT: {_format_ratio(self.false_roi_rate)}",
            f"- Gate average latency: {self.gate_average_latency_ms:.3f} ms",
            f"- Gate max latency: {self.gate_max_latency_ms:.3f} ms",
            "",
            "## Counts",
            "",
            f"- Frames: {self.frame_count}",
            f"- Target GT objects: {self.target_gt_count}",
            f"- Target GT frames: {self.target_gt_frame_count}",
            f"- ROI records: {self.roi_record_count}",
            f"- ROI frames: {self.roi_frame_count}",
            f"- Full-frame input pixel area: {self.full_frame_input_pixel_area}",
            f"- ROI-only input pixel area: {self.roi_only_input_pixel_area}",
            f"- Effective input pixel area: {self.effective_input_pixel_area}",
            "",
            "## Inputs",
            "",
        ]
        for key, value in self.inputs.to_json_dict().items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
        return "\n".join(lines)


def build_roi_proposal_report(
    inputs: RoiProposalInputs,
    ground_truth: Iterable[GroundTruthAnnotation],
    roi_records: Iterable[ROIMetadata],
    frame_records: Iterable[GateFrameMetadata],
    target_classes: Iterable[str] | None = None,
) -> RoiProposalReport:
    normalized_targets = normalize_target_classes(target_classes)
    gt_records = filter_gt_by_target_classes(ground_truth, normalized_targets)
    rois = list(roi_records)
    frames = list(frame_records)
    rois_by_frame = _group_by_frame(rois)
    gt_by_frame = _group_by_frame(gt_records)

    contained_gt_count = 0
    missed_target_frames: set[tuple[str, int]] = set()
    for gt in gt_records:
        key = (gt.camera_id, gt.frame_id)
        frame_rois = rois_by_frame.get(key, [])
        if any(contains_bbox(roi_record.roi, gt.bbox_xyxy) for roi_record in frame_rois):
            contained_gt_count += 1
        else:
            missed_target_frames.add(key)

    no_roi_target_frame_count = sum(
        1 for key in gt_by_frame if not rois_by_frame.get(key)
    )
    false_roi_count = 0
    for roi_record in rois:
        frame_gt = gt_by_frame.get((roi_record.camera_id, roi_record.frame_id), [])
        if not any(contains_bbox(roi_record.roi, gt.bbox_xyxy) for gt in frame_gt):
            false_roi_count += 1

    full_frame_input_area = sum(frame.original_frame_size.area() for frame in frames)
    roi_area_by_frame = {
        key: sum(roi_record.roi.area() for roi_record in frame_rois)
        for key, frame_rois in rois_by_frame.items()
    }
    roi_only_input_area = sum(roi_area_by_frame.values())
    effective_input_area = 0
    area_ratios: list[float] = []
    latencies = [frame.gate_latency_ms for frame in frames]

    for frame in frames:
        key = (frame.camera_id, frame.frame_id)
        frame_area = frame.original_frame_size.area()
        roi_area = roi_area_by_frame.get(key, 0)
        effective_input_area += roi_area
        if frame.should_run_full_frame:
            effective_input_area += frame_area
        area_ratios.append(roi_area / frame_area if frame_area else 0.0)

    return RoiProposalReport(
        inputs=inputs,
        target_classes=tuple(target_classes or ()),
        frame_count=len(frames),
        target_gt_count=len(gt_records),
        contained_gt_count=contained_gt_count,
        target_gt_frame_count=len(gt_by_frame),
        no_roi_target_frame_count=no_roi_target_frame_count,
        missed_target_frame_count=len(missed_target_frames),
        roi_record_count=len(rois),
        roi_frame_count=len(rois_by_frame),
        false_roi_count=false_roi_count,
        full_frame_check_frame_count=sum(1 for frame in frames if frame.should_run_full_frame),
        fallback_frame_count=sum(1 for frame in frames if frame.trigger_type == TriggerType.FALLBACK_FULL_FRAME),
        full_frame_input_pixel_area=full_frame_input_area,
        roi_only_input_pixel_area=roi_only_input_area,
        effective_input_pixel_area=effective_input_area,
        average_roi_count_per_frame=(len(rois) / len(frames) if frames else 0.0),
        average_total_roi_area_ratio_per_frame=(sum(area_ratios) / len(area_ratios) if area_ratios else 0.0),
        max_total_roi_area_ratio_per_frame=(max(area_ratios) if area_ratios else 0.0),
        gate_average_latency_ms=(sum(latencies) / len(latencies) if latencies else 0.0),
        gate_max_latency_ms=(max(latencies) if latencies else 0.0),
    )


def write_roi_proposal_report_json(report: RoiProposalReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(report.to_json_dict(), file, ensure_ascii=False, indent=2)
        file.write("\n")


def write_roi_proposal_report_markdown(report: RoiProposalReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.to_markdown(), encoding="utf-8")


def _group_by_frame(records):
    grouped = defaultdict(list)
    for record in records:
        grouped[(record.camera_id, record.frame_id)].append(record)
    return dict(grouped)


def _reduction_ratio(baseline: int, current: int) -> float:
    if baseline == 0:
        return 0.0
    return (baseline - current) / baseline


def _format_ratio(value: float) -> str:
    return f"{value:.3f} ({value * 100:.1f}%)"
