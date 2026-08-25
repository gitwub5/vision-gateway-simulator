"""Target-aware ROI proposal validation metrics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common import GateFrameMetadata, GroundTruthAnnotation, ROIMetadata, TriggerType
from common.io import write_json, write_text
from common.records import format_ratio, group_by_frame
from evaluation.metrics.class_filter import filter_gt_by_target_classes, normalize_target_classes
from evaluation.metrics.roi_containment import contains_bbox
from roi_generator.observability.trace import TileMetadataRecord


@dataclass(frozen=True)
class RoiProposalInputs:
    ground_truth: Path
    roi_metadata: Path
    frame_metadata: Path
    report_json: Path
    report_markdown: Path
    tile_metadata: Path | None = None

    def to_json_dict(self) -> dict[str, str]:
        data = {
            "ground_truth": str(self.ground_truth),
            "roi_metadata": str(self.roi_metadata),
            "frame_metadata": str(self.frame_metadata),
            "report_json": str(self.report_json),
            "report_markdown": str(self.report_markdown),
        }
        if self.tile_metadata is not None:
            data["tile_metadata"] = str(self.tile_metadata)
        return data


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
    average_roi_batch_slots_used_per_frame: float
    average_tile_group_count_per_frame: float
    average_estimated_tensor_pixels_per_frame: float
    average_tensor_batch_cost_per_frame: float
    gate_average_latency_ms: float
    gate_max_latency_ms: float
    tile_record_count: int = 0
    selected_tile_count: int = 0
    average_selected_tile_count_per_frame: float = 0.0
    average_selected_tile_area_ratio_per_frame: float = 0.0
    target_gt_tile_contained_count: int = 0
    false_tile_count: int = 0
    average_raw_component_count_per_frame: float = 0.0
    average_filtered_component_count_per_frame: float = 0.0
    average_merged_roi_count_per_frame: float = 0.0
    average_motion_density_per_frame: float = 0.0
    average_final_roi_area_ratio_per_frame: float = 0.0
    policy_label_counts: dict[str, int] = field(default_factory=dict)
    decision_reason_counts: dict[str, int] = field(default_factory=dict)

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
    def target_gt_tile_containment(self) -> float:
        if self.target_gt_count == 0:
            return 0.0
        return self.target_gt_tile_contained_count / self.target_gt_count

    @property
    def false_tile_ratio(self) -> float:
        if self.selected_tile_count == 0:
            return 0.0
        return self.false_tile_count / self.selected_tile_count

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
        data["target_gt_tile_containment"] = self.target_gt_tile_containment
        data["false_tile_ratio"] = self.false_tile_ratio
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
            f"- Target GT ROI containment: {format_ratio(self.target_gt_roi_containment)}",
            f"- Missed target GT objects: {self.missed_gt_count}",
            f"- No-ROI target frames: {self.no_roi_target_frame_count}",
            f"- Missed target frames: {self.missed_target_frame_count}",
            f"- ROI-only input area reduction: {format_ratio(self.roi_only_input_area_reduction)}",
            f"- Effective input area reduction including full-frame checks: {format_ratio(self.effective_input_area_reduction)}",
            f"- Average ROI count per frame: {self.average_roi_count_per_frame:.3f}",
            f"- Average ROI batch slots per frame: {self.average_roi_batch_slots_used_per_frame:.3f}",
            f"- Average tile groups per frame: {self.average_tile_group_count_per_frame:.3f}",
            f"- Average tensor batch cost per frame: {self.average_tensor_batch_cost_per_frame:.3f}",
            f"- Average total ROI area ratio per frame: {format_ratio(self.average_total_roi_area_ratio_per_frame)}",
            f"- Max total ROI area ratio per frame: {format_ratio(self.max_total_roi_area_ratio_per_frame)}",
            f"- Full-frame check rate: {format_ratio(self.full_frame_check_rate)}",
            f"- Fallback frame rate: {format_ratio(self.fallback_frame_rate)}",
            f"- False ROI rate against target GT: {format_ratio(self.false_roi_rate)}",
            f"- Target GT tile containment: {format_ratio(self.target_gt_tile_containment)}",
            f"- False tile ratio against target GT: {format_ratio(self.false_tile_ratio)}",
            f"- Average selected tile count per frame: {self.average_selected_tile_count_per_frame:.3f}",
            f"- Average selected tile area ratio per frame: {format_ratio(self.average_selected_tile_area_ratio_per_frame)}",
            f"- Average raw component count per frame: {self.average_raw_component_count_per_frame:.3f}",
            f"- Average filtered component count per frame: {self.average_filtered_component_count_per_frame:.3f}",
            f"- Average merged ROI count per frame: {self.average_merged_roi_count_per_frame:.3f}",
            f"- Average motion density per frame: {format_ratio(self.average_motion_density_per_frame)}",
            f"- Average final ROI area ratio per frame: {format_ratio(self.average_final_roi_area_ratio_per_frame)}",
            f"- Gate average latency: {self.gate_average_latency_ms:.3f} ms",
            f"- Gate max latency: {self.gate_max_latency_ms:.3f} ms",
            "",
            "## Policy Labels",
            "",
        ]
        for policy_label, count in sorted(self.policy_label_counts.items()):
            lines.append(f"- `{policy_label}`: {count}")
        lines.extend([
            "",
            "## Counts",
            "",
            f"- Frames: {self.frame_count}",
            f"- Target GT objects: {self.target_gt_count}",
            f"- Target GT frames: {self.target_gt_frame_count}",
            f"- ROI records: {self.roi_record_count}",
            f"- ROI frames: {self.roi_frame_count}",
            f"- Tile records: {self.tile_record_count}",
            f"- Selected tile records: {self.selected_tile_count}",
            f"- Full-frame input pixel area: {self.full_frame_input_pixel_area}",
            f"- ROI-only input pixel area: {self.roi_only_input_pixel_area}",
            f"- Effective input pixel area: {self.effective_input_pixel_area}",
            "",
            "## Decision Reasons",
            "",
        ])
        for reason, count in sorted(self.decision_reason_counts.items()):
            lines.append(f"- `{reason}`: {count}")
        lines.extend([
            "",
            "## Inputs",
            "",
        ])
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
    tile_records: Iterable[TileMetadataRecord] | None = None,
) -> RoiProposalReport:
    normalized_targets = normalize_target_classes(target_classes)
    gt_records = filter_gt_by_target_classes(ground_truth, normalized_targets)
    rois = list(roi_records)
    frames = list(frame_records)
    tiles = list(tile_records or [])
    rois_by_frame = group_by_frame(rois)
    gt_by_frame = group_by_frame(gt_records)
    selected_tiles = [tile for tile in tiles if tile.tile.selected]
    selected_tiles_by_frame = group_by_frame(selected_tiles)
    selected_tile_count_total = len(selected_tiles) if tiles else sum(frame.selected_tile_count for frame in frames)

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

    target_gt_tile_contained_count = 0
    for gt in gt_records:
        frame_tiles = selected_tiles_by_frame.get((gt.camera_id, gt.frame_id), [])
        if any(contains_bbox(tile.tile.bbox, gt.bbox_xyxy) for tile in frame_tiles):
            target_gt_tile_contained_count += 1

    false_tile_count = 0
    for tile in selected_tiles:
        frame_gt = gt_by_frame.get((tile.camera_id, tile.frame_id), [])
        if not any(contains_bbox(tile.tile.bbox, gt.bbox_xyxy) for gt in frame_gt):
            false_tile_count += 1

    full_frame_input_area = sum(frame.original_frame_size.area() for frame in frames)
    roi_area_by_frame = {
        key: sum(roi_record.roi.area() for roi_record in frame_rois)
        for key, frame_rois in rois_by_frame.items()
    }
    roi_only_input_area = sum(roi_area_by_frame.values())
    recalculated_effective_input_area = 0
    area_ratios: list[float] = []
    selected_tile_area_ratios: list[float] = []
    latencies = [frame.gate_latency_ms for frame in frames]
    policy_label_counts = Counter(frame.policy_label or "unknown" for frame in frames)
    decision_reason_counts = Counter(frame.decision_reason or "unknown" for frame in frames)

    for frame in frames:
        key = (frame.camera_id, frame.frame_id)
        frame_area = frame.original_frame_size.area()
        roi_area = roi_area_by_frame.get(key, 0)
        recalculated_effective_input_area += roi_area
        if frame.should_run_full_frame:
            recalculated_effective_input_area += frame_area
        area_ratios.append(roi_area / frame_area if frame_area else 0.0)
        selected_tile_area = sum(tile.tile.bbox.area() for tile in selected_tiles_by_frame.get(key, []))
        selected_tile_area_ratios.append(selected_tile_area / frame_area if frame_area else 0.0)
    metadata_effective_input_area = sum(frame.effective_input_area for frame in frames)
    effective_input_area = metadata_effective_input_area or recalculated_effective_input_area

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
        average_roi_batch_slots_used_per_frame=_average(frame.roi_batch_slots_used for frame in frames),
        average_tile_group_count_per_frame=_average(frame.tile_group_count for frame in frames),
        average_estimated_tensor_pixels_per_frame=_average(frame.estimated_tensor_pixels for frame in frames),
        average_tensor_batch_cost_per_frame=_average(frame.tensor_batch_cost for frame in frames),
        tile_record_count=len(tiles),
        selected_tile_count=selected_tile_count_total,
        average_selected_tile_count_per_frame=(selected_tile_count_total / len(frames) if frames else 0.0),
        average_selected_tile_area_ratio_per_frame=(
            sum(selected_tile_area_ratios) / len(selected_tile_area_ratios) if selected_tile_area_ratios else 0.0
        ),
        target_gt_tile_contained_count=target_gt_tile_contained_count,
        false_tile_count=false_tile_count,
        average_raw_component_count_per_frame=_average(frame.raw_component_count for frame in frames),
        average_filtered_component_count_per_frame=_average(frame.filtered_component_count for frame in frames),
        average_merged_roi_count_per_frame=_average(frame.merged_roi_count for frame in frames),
        average_motion_density_per_frame=_average(frame.motion_density for frame in frames),
        average_final_roi_area_ratio_per_frame=_average(frame.final_roi_area_ratio for frame in frames),
        policy_label_counts=dict(policy_label_counts),
        decision_reason_counts=dict(decision_reason_counts),
        gate_average_latency_ms=(sum(latencies) / len(latencies) if latencies else 0.0),
        gate_max_latency_ms=(max(latencies) if latencies else 0.0),
    )


def write_roi_proposal_report_json(report: RoiProposalReport, output_path: str | Path) -> None:
    write_json(report.to_json_dict(), output_path)


def write_roi_proposal_report_markdown(report: RoiProposalReport, output_path: str | Path) -> None:
    write_text(report.to_markdown(), output_path)


def write_roi_policy_summary_markdown(report: RoiProposalReport, output_path: str | Path) -> None:
    lines = [
        "# ROI Policy Summary",
        "",
        "## Policy Labels",
        "",
    ]
    for policy_label, count in sorted(report.policy_label_counts.items()):
        lines.append(f"- `{policy_label}`: {count}")
    lines.extend([
        "",
        "## Target Coverage",
        "",
        f"- Target GT ROI containment: {format_ratio(report.target_gt_roi_containment)}",
        f"- Missed target GT objects: {report.missed_gt_count}",
        f"- No-ROI target frames: {report.no_roi_target_frame_count}",
        "",
        "## Policy Cost",
        "",
        f"- Effective input area reduction: {format_ratio(report.effective_input_area_reduction)}",
        f"- Average ROI count per frame: {report.average_roi_count_per_frame:.3f}",
        f"- Average ROI batch slots per frame: {report.average_roi_batch_slots_used_per_frame:.3f}",
        f"- Average selected tile count per frame: {report.average_selected_tile_count_per_frame:.3f}",
        f"- Average tile group count per frame: {report.average_tile_group_count_per_frame:.3f}",
        f"- Average tensor batch cost per frame: {report.average_tensor_batch_cost_per_frame:.3f}",
        "",
        "## Decision Reasons",
        "",
    ])
    for reason, count in sorted(report.decision_reason_counts.items()):
        lines.append(f"- `{reason}`: {count}")
    lines.append("")
    write_text("\n".join(lines), output_path)


def write_cost_summary_json(report: RoiProposalReport, output_path: str | Path) -> None:
    write_json(
        {
            "schema_version": 1,
            "frame_count": report.frame_count,
            "full_frame_input_pixel_area": report.full_frame_input_pixel_area,
            "roi_only_input_pixel_area": report.roi_only_input_pixel_area,
            "effective_input_pixel_area": report.effective_input_pixel_area,
            "roi_only_input_area_reduction": report.roi_only_input_area_reduction,
            "effective_input_area_reduction": report.effective_input_area_reduction,
            "average_roi_count_per_frame": report.average_roi_count_per_frame,
            "average_roi_batch_slots_used_per_frame": report.average_roi_batch_slots_used_per_frame,
            "average_tile_group_count_per_frame": report.average_tile_group_count_per_frame,
            "average_estimated_tensor_pixels_per_frame": report.average_estimated_tensor_pixels_per_frame,
            "average_tensor_batch_cost_per_frame": report.average_tensor_batch_cost_per_frame,
            "average_total_roi_area_ratio_per_frame": report.average_total_roi_area_ratio_per_frame,
            "max_total_roi_area_ratio_per_frame": report.max_total_roi_area_ratio_per_frame,
            "selected_tile_count": report.selected_tile_count,
            "average_selected_tile_count_per_frame": report.average_selected_tile_count_per_frame,
            "average_selected_tile_area_ratio_per_frame": report.average_selected_tile_area_ratio_per_frame,
            "average_raw_component_count_per_frame": report.average_raw_component_count_per_frame,
            "average_filtered_component_count_per_frame": report.average_filtered_component_count_per_frame,
            "average_merged_roi_count_per_frame": report.average_merged_roi_count_per_frame,
            "average_motion_density_per_frame": report.average_motion_density_per_frame,
            "average_final_roi_area_ratio_per_frame": report.average_final_roi_area_ratio_per_frame,
            "policy_label_counts": report.policy_label_counts,
            "decision_reason_counts": report.decision_reason_counts,
        },
        output_path,
    )


def _reduction_ratio(baseline: int, current: int) -> float:
    if baseline == 0:
        return 0.0
    return (baseline - current) / baseline


def _average(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)
