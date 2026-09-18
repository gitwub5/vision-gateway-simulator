"""Static zone prior + tracker memory + temporal refresh guard hybrid validation metrics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common import FrameSize, GroundTruthAnnotation, ROI
from common.io import write_json, write_text
from common.records import format_ratio, group_by_frame
from evaluation.metrics.roi_containment import contains_bbox


@dataclass(frozen=True)
class GridShape:
    columns: int
    rows: int

    @property
    def cell_count(self) -> int:
        return self.columns * self.rows

    def to_json_dict(self) -> dict[str, int]:
        return {"columns": self.columns, "rows": self.rows}


@dataclass(frozen=True)
class StaticTrackerHybridFrame:
    camera_id: str
    frame_id: int
    frame_index: int
    timestamp: float
    frame_size: FrameSize


@dataclass(frozen=True)
class StaticTrackerHybridProfile:
    name: str
    static_max_area_ratio: float
    static_dilation_cells: int
    refresh_interval: int
    margin_ratio: float
    guard_stale_frames: int
    max_rois: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StaticTrackerHybridFrameRecord:
    camera_id: str
    frame_id: int
    frame_index: int
    profile_name: str
    is_refresh_frame: bool
    guard_fallback: bool
    target_gt_count: int
    contained_gt_count: int
    combined_roi_count: int
    effective_input_area_ratio: float

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StaticTrackerHybridProfileReport:
    profile: StaticTrackerHybridProfile
    static_selected_area_ratio: float
    frame_count: int
    refresh_frame_count: int
    memory_frame_count: int
    guard_fallback_frame_count: int
    target_gt_count: int
    contained_gt_count: int
    memory_frame_target_gt_count: int
    memory_frame_contained_gt_count: int
    static_only_contained_gt_count: int
    full_frame_input_pixel_area: int
    effective_input_pixel_area: float
    average_combined_roi_count_per_memory_frame: float
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
    def static_only_memory_frame_gt_recall(self) -> float:
        if self.memory_frame_target_gt_count == 0:
            return 0.0
        return self.static_only_contained_gt_count / self.memory_frame_target_gt_count

    @property
    def static_recovered_gt_count(self) -> int:
        """GT contained by the combined ROI set but not by tracker memory alone."""
        return max(0, self.memory_frame_contained_gt_count - self.static_only_contained_gt_count)

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
        data["static_only_memory_frame_gt_recall"] = self.static_only_memory_frame_gt_recall
        data["static_recovered_gt_count"] = self.static_recovered_gt_count
        data["effective_input_area_ratio"] = self.effective_input_area_ratio
        data["effective_input_area_reduction"] = self.effective_input_area_reduction
        return data


@dataclass(frozen=True)
class StaticTrackerHybridReport:
    dataset_config: str
    experiment_name: str
    target_classes: tuple[str, ...]
    frame_count: int
    target_gt_count: int
    target_frame_count: int
    grid_shape: GridShape
    profiles: dict[str, StaticTrackerHybridProfileReport] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "dataset_config": self.dataset_config,
            "experiment_name": self.experiment_name,
            "target_classes": list(self.target_classes),
            "frame_count": self.frame_count,
            "target_gt_count": self.target_gt_count,
            "target_frame_count": self.target_frame_count,
            "grid_shape": self.grid_shape.to_json_dict(),
            "profiles": {
                name: profile.to_json_dict()
                for name, profile in self.profiles.items()
            },
        }

    def to_markdown(self) -> str:
        lines = [
            "# Static Zone Prior + Tracker Memory + Temporal Refresh Guard Hybrid Report",
            "",
            "## Scope",
            "",
            f"- Experiment: `{self.experiment_name}`",
            f"- Dataset config: `{self.dataset_config}`",
            f"- Target classes: `{', '.join(self.target_classes) if self.target_classes else 'all'}`",
            f"- Frames: {self.frame_count}",
            f"- Target frames: {self.target_frame_count}",
            f"- Target GT objects: {self.target_gt_count}",
            f"- Grid: {self.grid_shape.columns}x{self.grid_shape.rows}",
            "",
            "## Profile Comparison",
            "",
            (
                "| Profile | Static area | Full-frame call reduction | Effective input reduction | "
                "GT recall | Memory-frame GT recall | Static-only memory recall | Guard fallback frames | "
                "ROI/memory frame | Max miss run |"
            ),
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for profile in self.profiles.values():
            lines.append(
                "| "
                f"`{profile.profile.name}` | "
                f"{format_ratio(profile.static_selected_area_ratio)} | "
                f"{format_ratio(profile.full_frame_detector_call_reduction)} | "
                f"{format_ratio(profile.effective_input_area_reduction)} | "
                f"{format_ratio(profile.target_gt_recall)} | "
                f"{format_ratio(profile.memory_frame_target_gt_recall)} | "
                f"{format_ratio(profile.static_only_memory_frame_gt_recall)} | "
                f"{profile.guard_fallback_frame_count} | "
                f"{profile.average_combined_roi_count_per_memory_frame:.3f} | "
                f"{profile.max_consecutive_memory_miss_frames} |"
            )
        lines.append("")
        return "\n".join(lines)


def default_static_tracker_hybrid_profiles() -> list[StaticTrackerHybridProfile]:
    return [
        StaticTrackerHybridProfile(
            name="static10_refresh5_margin30_guard5",
            static_max_area_ratio=0.10,
            static_dilation_cells=1,
            refresh_interval=5,
            margin_ratio=0.30,
            guard_stale_frames=5,
        ),
        StaticTrackerHybridProfile(
            name="static10_refresh10_margin50_guard10",
            static_max_area_ratio=0.10,
            static_dilation_cells=1,
            refresh_interval=10,
            margin_ratio=0.50,
            guard_stale_frames=10,
        ),
        StaticTrackerHybridProfile(
            name="static20_refresh10_margin50_guard5",
            static_max_area_ratio=0.20,
            static_dilation_cells=1,
            refresh_interval=10,
            margin_ratio=0.50,
            guard_stale_frames=5,
        ),
        StaticTrackerHybridProfile(
            name="static20_refresh15_margin50_guard10",
            static_max_area_ratio=0.20,
            static_dilation_cells=1,
            refresh_interval=15,
            margin_ratio=0.50,
            guard_stale_frames=10,
        ),
        StaticTrackerHybridProfile(
            name="static10_refresh5_margin50_guard3",
            static_max_area_ratio=0.10,
            static_dilation_cells=1,
            refresh_interval=5,
            margin_ratio=0.50,
            guard_stale_frames=3,
        ),
    ]


def build_static_tracker_hybrid_report(
    frames: Iterable[StaticTrackerHybridFrame],
    ground_truth: Iterable[GroundTruthAnnotation],
    profiles: Iterable[StaticTrackerHybridProfile],
    grid_shape: GridShape,
    frame_size: FrameSize,
    dataset_config: str,
    experiment_name: str,
    target_classes: Iterable[str] | None = None,
) -> tuple[StaticTrackerHybridReport, list[StaticTrackerHybridFrameRecord]]:
    frame_records = list(frames)
    gt_records = list(ground_truth)
    gt_by_frame = group_by_frame(gt_records)
    cell_scores = _score_center_cells(gt_records, frame_size, grid_shape)
    profile_reports: dict[str, StaticTrackerHybridProfileReport] = {}
    all_records: list[StaticTrackerHybridFrameRecord] = []
    for profile in profiles:
        static_cells = _select_cells(
            cell_scores, grid_shape, profile.static_max_area_ratio, profile.static_dilation_cells
        )
        report, records = evaluate_static_tracker_hybrid_profile(
            frame_records, gt_by_frame, static_cells, grid_shape, profile
        )
        profile_reports[profile.name] = report
        all_records.extend(records)
    target_frames = {key for key, records in gt_by_frame.items() if records}
    return (
        StaticTrackerHybridReport(
            dataset_config=dataset_config,
            experiment_name=experiment_name,
            target_classes=tuple(target_classes or ()),
            frame_count=len(frame_records),
            target_gt_count=len(gt_records),
            target_frame_count=len(target_frames),
            grid_shape=grid_shape,
            profiles=profile_reports,
        ),
        all_records,
    )


def evaluate_static_tracker_hybrid_profile(
    frames: list[StaticTrackerHybridFrame],
    gt_by_frame: dict[tuple[str, int], list[GroundTruthAnnotation]],
    static_selected_cells: set[tuple[int, int]],
    grid_shape: GridShape,
    profile: StaticTrackerHybridProfile,
) -> tuple[StaticTrackerHybridProfileReport, list[StaticTrackerHybridFrameRecord]]:
    memory: list[tuple[int, ROI]] = []
    records: list[StaticTrackerHybridFrameRecord] = []
    full_frame_area = sum(frame.frame_size.area() for frame in frames)
    effective_area = 0.0
    combined_roi_counts: list[int] = []
    miss_runs: list[int] = []
    current_miss_run = 0
    contained_total = 0
    gt_total = 0
    memory_gt_total = 0
    memory_contained_total = 0
    static_only_contained_total = 0
    refresh_count = 0
    guard_fallback_count = 0
    static_area_ratios: list[float] = []

    for frame in frames:
        frame_gt = gt_by_frame.get((frame.camera_id, frame.frame_id), [])
        static_rects = _cells_to_rois(static_selected_cells, frame.frame_size, grid_shape)
        static_area_ratios.append(
            len(static_selected_cells) / grid_shape.cell_count if grid_shape.cell_count else 0.0
        )
        is_refresh = frame.frame_index % max(1, profile.refresh_interval) == 0
        guard_fallback = False
        if is_refresh:
            refresh_count += 1
            frame_rois = [_roi_from_bbox(gt.bbox_xyxy, frame.frame_size, profile.margin_ratio) for gt in frame_gt]
            memory = [(frame.frame_index, roi) for roi in _limit_rois(frame_rois, profile.max_rois)]
            contained = len(frame_gt)
            frame_effective_area = frame.frame_size.area()
            combined_count = 0
            if current_miss_run:
                miss_runs.append(current_miss_run)
                current_miss_run = 0
        else:
            valid_memory = [
                roi
                for source_index, roi in memory
                if frame.frame_index - source_index <= profile.guard_stale_frames
            ]
            guard_fallback = bool(memory) and not valid_memory
            if guard_fallback:
                guard_fallback_count += 1
            combined_rois = valid_memory + static_rects
            static_only_contained = sum(
                1 for gt in frame_gt if any(contains_bbox(roi, gt.bbox_xyxy) for roi in static_rects)
            )
            contained = sum(
                1 for gt in frame_gt if any(contains_bbox(roi, gt.bbox_xyxy) for roi in combined_rois)
            )
            memory_gt_total += len(frame_gt)
            memory_contained_total += contained
            static_only_contained_total += static_only_contained
            frame_effective_area = _union_area(combined_rois)
            combined_count = len(combined_rois)
            combined_roi_counts.append(combined_count)
            if contained < len(frame_gt):
                current_miss_run += 1
            elif current_miss_run:
                miss_runs.append(current_miss_run)
                current_miss_run = 0

        gt_total += len(frame_gt)
        contained_total += contained
        effective_area += frame_effective_area
        records.append(
            StaticTrackerHybridFrameRecord(
                camera_id=frame.camera_id,
                frame_id=frame.frame_id,
                frame_index=frame.frame_index,
                profile_name=profile.name,
                is_refresh_frame=is_refresh,
                guard_fallback=guard_fallback,
                target_gt_count=len(frame_gt),
                contained_gt_count=contained,
                combined_roi_count=0 if is_refresh else combined_count,
                effective_input_area_ratio=(
                    frame_effective_area / frame.frame_size.area() if frame.frame_size.area() else 0.0
                ),
            )
        )

    if current_miss_run:
        miss_runs.append(current_miss_run)

    report = StaticTrackerHybridProfileReport(
        profile=profile,
        static_selected_area_ratio=_average(static_area_ratios),
        frame_count=len(frames),
        refresh_frame_count=refresh_count,
        memory_frame_count=len(frames) - refresh_count,
        guard_fallback_frame_count=guard_fallback_count,
        target_gt_count=gt_total,
        contained_gt_count=contained_total,
        memory_frame_target_gt_count=memory_gt_total,
        memory_frame_contained_gt_count=memory_contained_total,
        static_only_contained_gt_count=static_only_contained_total,
        full_frame_input_pixel_area=full_frame_area,
        effective_input_pixel_area=effective_area,
        average_combined_roi_count_per_memory_frame=_average(combined_roi_counts),
        max_consecutive_memory_miss_frames=max(miss_runs, default=0),
    )
    return report, records


def write_static_tracker_hybrid_report_json(report: StaticTrackerHybridReport, output_path: str | Path) -> None:
    write_json(report.to_json_dict(), output_path)


def write_static_tracker_hybrid_report_markdown(report: StaticTrackerHybridReport, output_path: str | Path) -> None:
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


def _cells_to_rois(cells: set[tuple[int, int]], frame_size: FrameSize, grid_shape: GridShape) -> list[ROI]:
    rois: list[ROI] = []
    for row, column in cells:
        x1 = round(column * frame_size.width / grid_shape.columns)
        x2 = round((column + 1) * frame_size.width / grid_shape.columns)
        y1 = round(row * frame_size.height / grid_shape.rows)
        y2 = round((row + 1) * frame_size.height / grid_shape.rows)
        rois.append(ROI(x=x1, y=y1, w=max(0, x2 - x1), h=max(0, y2 - y1)))
    return rois


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


def _score_center_cells(
    ground_truth: list[GroundTruthAnnotation],
    frame_size: FrameSize,
    grid_shape: GridShape,
) -> Counter[tuple[int, int]]:
    scores: Counter[tuple[int, int]] = Counter()
    for gt in ground_truth:
        scores[_center_cell(gt.bbox_xyxy, frame_size, grid_shape)] += 1
    return scores


def _select_cells(
    cell_scores: Counter[tuple[int, int]],
    grid_shape: GridShape,
    max_area_ratio: float,
    dilation_cells: int,
) -> set[tuple[int, int]]:
    base_count = max(1, round(grid_shape.cell_count * max_area_ratio))
    ranked_cells = sorted(
        _all_cells(grid_shape),
        key=lambda cell: (-cell_scores.get(cell, 0), cell[0], cell[1]),
    )
    selected = set(ranked_cells[:base_count])
    if dilation_cells <= 0:
        return selected
    return _dilate_cells(selected, grid_shape, dilation_cells)


def _center_cell(
    bbox_xyxy: list[float],
    frame_size: FrameSize,
    grid_shape: GridShape,
) -> tuple[int, int]:
    x1, y1, x2, y2 = bbox_xyxy
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    return _point_cell(center_x, center_y, frame_size, grid_shape)


def _point_cell(
    x: float,
    y: float,
    frame_size: FrameSize,
    grid_shape: GridShape,
) -> tuple[int, int]:
    column = _axis_cell(x, frame_size.width, grid_shape.columns)
    row = _axis_cell(y, frame_size.height, grid_shape.rows)
    return row, column


def _axis_cell(value: float, axis_size: int, cell_count: int) -> int:
    if axis_size <= 0 or cell_count <= 0:
        return 0
    normalized = min(max(value / axis_size, 0.0), 0.999999)
    return min(cell_count - 1, int(normalized * cell_count))


def _all_cells(grid_shape: GridShape) -> list[tuple[int, int]]:
    return [
        (row, column)
        for row in range(grid_shape.rows)
        for column in range(grid_shape.columns)
    ]


def _dilate_cells(
    cells: set[tuple[int, int]],
    grid_shape: GridShape,
    radius: int,
) -> set[tuple[int, int]]:
    dilated: set[tuple[int, int]] = set()
    for row, column in cells:
        for row_delta in range(-radius, radius + 1):
            for column_delta in range(-radius, radius + 1):
                candidate = (row + row_delta, column + column_delta)
                if _cell_in_grid(candidate, grid_shape):
                    dilated.add(candidate)
    return dilated


def _cell_in_grid(cell: tuple[int, int], grid_shape: GridShape) -> bool:
    row, column = cell
    return 0 <= row < grid_shape.rows and 0 <= column < grid_shape.columns
