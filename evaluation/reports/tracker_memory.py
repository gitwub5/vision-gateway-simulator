"""Feedback / tracker-memory POC metrics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common import FrameSize, GroundTruthAnnotation, ROI
from common.io import write_json, write_text
from common.records import format_ratio, group_by_frame
from evaluation.metrics.roi_containment import contains_bbox


@dataclass(frozen=True)
class TrackerMemoryFrame:
    camera_id: str
    frame_id: int
    frame_index: int
    timestamp: float
    frame_size: FrameSize


@dataclass(frozen=True)
class TrackerMemoryProfile:
    name: str
    refresh_interval: int
    margin_ratio: float
    ttl_frames: int
    max_rois: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrackerMemoryFrameRecord:
    camera_id: str
    frame_id: int
    frame_index: int
    profile_name: str
    is_refresh_frame: bool
    target_gt_count: int
    contained_gt_count: int
    memory_roi_count: int
    memory_roi_area_ratio: float
    effective_input_area_ratio: float

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrackerMemoryProfileReport:
    profile: TrackerMemoryProfile
    frame_count: int
    refresh_frame_count: int
    memory_frame_count: int
    target_gt_count: int
    contained_gt_count: int
    memory_frame_target_gt_count: int
    memory_frame_contained_gt_count: int
    full_frame_input_pixel_area: int
    effective_input_pixel_area: float
    average_memory_roi_count_per_memory_frame: float
    average_memory_roi_area_ratio_per_memory_frame: float
    max_consecutive_memory_miss_frames: int

    @property
    def refresh_frame_rate(self) -> float:
        if self.frame_count == 0:
            return 0.0
        return self.refresh_frame_count / self.frame_count

    @property
    def full_frame_detector_call_reduction(self) -> float:
        return 1.0 - self.refresh_frame_rate

    @property
    def target_gt_recall(self) -> float:
        if self.target_gt_count == 0:
            return 0.0
        return self.contained_gt_count / self.target_gt_count

    @property
    def memory_frame_target_gt_recall(self) -> float:
        if self.memory_frame_target_gt_count == 0:
            return 0.0
        return self.memory_frame_contained_gt_count / self.memory_frame_target_gt_count

    @property
    def effective_input_area_ratio(self) -> float:
        if self.full_frame_input_pixel_area == 0:
            return 0.0
        return self.effective_input_pixel_area / self.full_frame_input_pixel_area

    @property
    def effective_input_area_reduction(self) -> float:
        return 1.0 - self.effective_input_area_ratio

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["profile"] = self.profile.to_json_dict()
        data["refresh_frame_rate"] = self.refresh_frame_rate
        data["full_frame_detector_call_reduction"] = self.full_frame_detector_call_reduction
        data["target_gt_recall"] = self.target_gt_recall
        data["memory_frame_target_gt_recall"] = self.memory_frame_target_gt_recall
        data["effective_input_area_ratio"] = self.effective_input_area_ratio
        data["effective_input_area_reduction"] = self.effective_input_area_reduction
        return data


@dataclass(frozen=True)
class TrackerMemoryReport:
    dataset_config: str
    experiment_name: str
    target_classes: tuple[str, ...]
    frame_count: int
    target_gt_count: int
    target_frame_count: int
    profiles: dict[str, TrackerMemoryProfileReport] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "dataset_config": self.dataset_config,
            "experiment_name": self.experiment_name,
            "target_classes": list(self.target_classes),
            "frame_count": self.frame_count,
            "target_gt_count": self.target_gt_count,
            "target_frame_count": self.target_frame_count,
            "profiles": {
                name: profile.to_json_dict()
                for name, profile in self.profiles.items()
            },
        }

    def to_markdown(self) -> str:
        lines = [
            "# Feedback / Tracker Memory POC Report",
            "",
            "## Scope",
            "",
            f"- Experiment: `{self.experiment_name}`",
            f"- Dataset config: `{self.dataset_config}`",
            f"- Target classes: `{', '.join(self.target_classes) if self.target_classes else 'all'}`",
            f"- Frames: {self.frame_count}",
            f"- Target frames: {self.target_frame_count}",
            f"- Target GT objects: {self.target_gt_count}",
            "",
            "## Profile Comparison",
            "",
            (
                "| Profile | Full-frame call reduction | Effective input reduction | "
                "GT recall | Memory-frame GT recall | ROI/memory frame | Max miss run |"
            ),
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for profile in self.profiles.values():
            lines.append(
                "| "
                f"`{profile.profile.name}` | "
                f"{format_ratio(profile.full_frame_detector_call_reduction)} | "
                f"{format_ratio(profile.effective_input_area_reduction)} | "
                f"{format_ratio(profile.target_gt_recall)} | "
                f"{format_ratio(profile.memory_frame_target_gt_recall)} | "
                f"{profile.average_memory_roi_count_per_memory_frame:.3f} | "
                f"{profile.max_consecutive_memory_miss_frames} |"
            )
        lines.append("")
        return "\n".join(lines)


def default_tracker_memory_profiles() -> list[TrackerMemoryProfile]:
    return [
        TrackerMemoryProfile(name="refresh_2_margin_30", refresh_interval=2, margin_ratio=0.30, ttl_frames=2),
        TrackerMemoryProfile(name="refresh_5_margin_30", refresh_interval=5, margin_ratio=0.30, ttl_frames=5),
        TrackerMemoryProfile(name="refresh_10_margin_30", refresh_interval=10, margin_ratio=0.30, ttl_frames=10),
        TrackerMemoryProfile(name="refresh_15_margin_30", refresh_interval=15, margin_ratio=0.30, ttl_frames=15),
        TrackerMemoryProfile(name="refresh_5_margin_50", refresh_interval=5, margin_ratio=0.50, ttl_frames=5),
        TrackerMemoryProfile(name="refresh_10_margin_50", refresh_interval=10, margin_ratio=0.50, ttl_frames=10),
    ]


def build_tracker_memory_report(
    frames: Iterable[TrackerMemoryFrame],
    ground_truth: Iterable[GroundTruthAnnotation],
    profiles: Iterable[TrackerMemoryProfile],
    dataset_config: str,
    experiment_name: str,
    target_classes: Iterable[str] | None = None,
) -> tuple[TrackerMemoryReport, list[TrackerMemoryFrameRecord]]:
    frame_records = list(frames)
    gt_records = list(ground_truth)
    gt_by_frame = group_by_frame(gt_records)
    profile_reports: dict[str, TrackerMemoryProfileReport] = {}
    all_frame_results: list[TrackerMemoryFrameRecord] = []
    for profile in profiles:
        report, records = evaluate_tracker_memory_profile(frame_records, gt_by_frame, profile)
        profile_reports[profile.name] = report
        all_frame_results.extend(records)
    target_frames = {key for key, records in gt_by_frame.items() if records}
    return (
        TrackerMemoryReport(
            dataset_config=dataset_config,
            experiment_name=experiment_name,
            target_classes=tuple(target_classes or ()),
            frame_count=len(frame_records),
            target_gt_count=len(gt_records),
            target_frame_count=len(target_frames),
            profiles=profile_reports,
        ),
        all_frame_results,
    )


def evaluate_tracker_memory_profile(
    frames: list[TrackerMemoryFrame],
    gt_by_frame: dict[tuple[str, int], list[GroundTruthAnnotation]],
    profile: TrackerMemoryProfile,
) -> tuple[TrackerMemoryProfileReport, list[TrackerMemoryFrameRecord]]:
    memory: list[tuple[int, ROI]] = []
    records: list[TrackerMemoryFrameRecord] = []
    full_frame_area = sum(frame.frame_size.area() for frame in frames)
    effective_area = 0.0
    memory_roi_counts: list[int] = []
    memory_roi_area_ratios: list[float] = []
    miss_runs: list[int] = []
    current_miss_run = 0
    contained_total = 0
    gt_total = 0
    memory_gt_total = 0
    memory_contained_total = 0
    refresh_count = 0

    for frame in frames:
        frame_gt = gt_by_frame.get((frame.camera_id, frame.frame_id), [])
        is_refresh = frame.frame_index % max(1, profile.refresh_interval) == 0
        if is_refresh:
            refresh_count += 1
            frame_rois = [_roi_from_bbox(gt.bbox_xyxy, frame.frame_size, profile.margin_ratio) for gt in frame_gt]
            memory = [(frame.frame_index, roi) for roi in _limit_rois(frame_rois, profile.max_rois)]
            contained = len(frame_gt)
            frame_effective_area = frame.frame_size.area()
            if current_miss_run:
                miss_runs.append(current_miss_run)
                current_miss_run = 0
        else:
            frame_rois = [
                roi
                for source_index, roi in memory
                if frame.frame_index - source_index <= profile.ttl_frames
            ]
            contained = sum(1 for gt in frame_gt if any(contains_bbox(roi, gt.bbox_xyxy) for roi in frame_rois))
            memory_gt_total += len(frame_gt)
            memory_contained_total += contained
            frame_effective_area = _union_area(frame_rois)
            memory_roi_counts.append(len(frame_rois))
            area_ratio = frame_effective_area / frame.frame_size.area() if frame.frame_size.area() else 0.0
            memory_roi_area_ratios.append(area_ratio)
            if contained < len(frame_gt):
                current_miss_run += 1
            elif current_miss_run:
                miss_runs.append(current_miss_run)
                current_miss_run = 0

        gt_total += len(frame_gt)
        contained_total += contained
        effective_area += frame_effective_area
        records.append(
            TrackerMemoryFrameRecord(
                camera_id=frame.camera_id,
                frame_id=frame.frame_id,
                frame_index=frame.frame_index,
                profile_name=profile.name,
                is_refresh_frame=is_refresh,
                target_gt_count=len(frame_gt),
                contained_gt_count=contained,
                memory_roi_count=0 if is_refresh else len(frame_rois),
                memory_roi_area_ratio=0.0 if is_refresh else (
                    frame_effective_area / frame.frame_size.area() if frame.frame_size.area() else 0.0
                ),
                effective_input_area_ratio=(
                    frame_effective_area / frame.frame_size.area() if frame.frame_size.area() else 0.0
                ),
            )
        )

    if current_miss_run:
        miss_runs.append(current_miss_run)

    report = TrackerMemoryProfileReport(
        profile=profile,
        frame_count=len(frames),
        refresh_frame_count=refresh_count,
        memory_frame_count=len(frames) - refresh_count,
        target_gt_count=gt_total,
        contained_gt_count=contained_total,
        memory_frame_target_gt_count=memory_gt_total,
        memory_frame_contained_gt_count=memory_contained_total,
        full_frame_input_pixel_area=full_frame_area,
        effective_input_pixel_area=effective_area,
        average_memory_roi_count_per_memory_frame=_average(memory_roi_counts),
        average_memory_roi_area_ratio_per_memory_frame=_average(memory_roi_area_ratios),
        max_consecutive_memory_miss_frames=max(miss_runs, default=0),
    )
    return report, records


def write_tracker_memory_report_json(report: TrackerMemoryReport, output_path: str | Path) -> None:
    write_json(report.to_json_dict(), output_path)


def write_tracker_memory_report_markdown(report: TrackerMemoryReport, output_path: str | Path) -> None:
    write_text(report.to_markdown(), output_path)


def _roi_from_bbox(bbox_xyxy: list[float], frame_size: FrameSize, margin_ratio: float) -> ROI:
    x1, y1, x2, y2 = bbox_xyxy
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    margin_x = width * margin_ratio
    margin_y = height * margin_ratio
    left = max(0, int(x1 - margin_x))
    top = max(0, int(y1 - margin_y))
    right = min(frame_size.width, int(x2 + margin_x + 0.999999))
    bottom = min(frame_size.height, int(y2 + margin_y + 0.999999))
    return ROI(x=left, y=top, w=max(0, right - left), h=max(0, bottom - top))


def _limit_rois(rois: list[ROI], max_rois: int | None) -> list[ROI]:
    if max_rois is None or max_rois <= 0:
        return rois
    return sorted(rois, key=lambda roi: roi.area(), reverse=True)[:max_rois]


def _union_area(rois: list[ROI]) -> int:
    rectangles = [
        (roi.x, roi.y, roi.x + roi.w, roi.y + roi.h)
        for roi in rois
        if roi.w > 0 and roi.h > 0
    ]
    if not rectangles:
        return 0
    xs = sorted({x for rect in rectangles for x in (rect[0], rect[2])})
    area = 0
    for left, right in zip(xs, xs[1:]):
        if right <= left:
            continue
        intervals = [
            (top, bottom)
            for x1, top, x2, bottom in rectangles
            if x1 < right and x2 > left
        ]
        area += (right - left) * _union_interval_length(intervals)
    return area


def _union_interval_length(intervals: list[tuple[int, int]]) -> int:
    if not intervals:
        return 0
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return sum(end - start for start, end in merged)


def _average(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)
