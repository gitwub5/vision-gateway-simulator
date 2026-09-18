"""Static zone / camera-prior POC metrics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common import FrameSize, GroundTruthAnnotation
from common.io import write_json, write_text
from common.records import format_ratio, group_by_frame


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
class StaticZoneProfile:
    name: str
    max_area_ratio: float
    dilation_cells: int = 0

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StaticZoneCellRecord:
    row: int
    column: int
    center_hit_count: int
    selected_profiles: tuple[str, ...] = ()

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["selected_profiles"] = list(self.selected_profiles)
        return data


@dataclass(frozen=True)
class StaticZoneProfileReport:
    profile: StaticZoneProfile
    selected_cell_count: int
    selected_area_ratio: float
    target_gt_count: int
    center_contained_gt_count: int
    bbox_contained_gt_count: int
    target_frame_count: int
    center_contained_target_frame_count: int
    bbox_contained_target_frame_count: int

    @property
    def input_area_reduction(self) -> float:
        return 1.0 - self.selected_area_ratio

    @property
    def center_gt_recall(self) -> float:
        if self.target_gt_count == 0:
            return 0.0
        return self.center_contained_gt_count / self.target_gt_count

    @property
    def bbox_gt_recall(self) -> float:
        if self.target_gt_count == 0:
            return 0.0
        return self.bbox_contained_gt_count / self.target_gt_count

    @property
    def center_target_frame_recall(self) -> float:
        if self.target_frame_count == 0:
            return 0.0
        return self.center_contained_target_frame_count / self.target_frame_count

    @property
    def bbox_target_frame_recall(self) -> float:
        if self.target_frame_count == 0:
            return 0.0
        return self.bbox_contained_target_frame_count / self.target_frame_count

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["profile"] = self.profile.to_json_dict()
        data["input_area_reduction"] = self.input_area_reduction
        data["center_gt_recall"] = self.center_gt_recall
        data["bbox_gt_recall"] = self.bbox_gt_recall
        data["center_target_frame_recall"] = self.center_target_frame_recall
        data["bbox_target_frame_recall"] = self.bbox_target_frame_recall
        return data


@dataclass(frozen=True)
class StaticZonePriorReport:
    dataset_config: str
    experiment_name: str
    target_classes: tuple[str, ...]
    frame_count: int
    frame_size: FrameSize
    grid_shape: GridShape
    target_gt_count: int
    target_frame_count: int
    occupied_cell_count: int
    profiles: dict[str, StaticZoneProfileReport] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "dataset_config": self.dataset_config,
            "experiment_name": self.experiment_name,
            "target_classes": list(self.target_classes),
            "frame_count": self.frame_count,
            "frame_size": self.frame_size.as_list(),
            "grid_shape": self.grid_shape.to_json_dict(),
            "target_gt_count": self.target_gt_count,
            "target_frame_count": self.target_frame_count,
            "occupied_cell_count": self.occupied_cell_count,
            "occupied_cell_ratio": (
                self.occupied_cell_count / self.grid_shape.cell_count
                if self.grid_shape.cell_count
                else 0.0
            ),
            "profiles": {
                name: profile.to_json_dict()
                for name, profile in self.profiles.items()
            },
        }

    def to_markdown(self) -> str:
        lines = [
            "# Static Zone / Camera Prior POC Report",
            "",
            "## Scope",
            "",
            f"- Experiment: `{self.experiment_name}`",
            f"- Dataset config: `{self.dataset_config}`",
            f"- Target classes: `{', '.join(self.target_classes) if self.target_classes else 'all'}`",
            f"- Frames: {self.frame_count}",
            f"- Frame size: {self.frame_size.width}x{self.frame_size.height}",
            f"- Grid: {self.grid_shape.columns}x{self.grid_shape.rows}",
            f"- Target frames: {self.target_frame_count}",
            f"- Target GT objects: {self.target_gt_count}",
            f"- Occupied cells: {self.occupied_cell_count}/{self.grid_shape.cell_count}",
            "",
            "## Profile Comparison",
            "",
            (
                "| Profile | Selected area | Area reduction | Center GT recall | "
                "BBox GT recall | Center frame recall | BBox frame recall |"
            ),
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for profile in self.profiles.values():
            lines.append(
                "| "
                f"`{profile.profile.name}` | "
                f"{format_ratio(profile.selected_area_ratio)} | "
                f"{format_ratio(profile.input_area_reduction)} | "
                f"{format_ratio(profile.center_gt_recall)} | "
                f"{format_ratio(profile.bbox_gt_recall)} | "
                f"{format_ratio(profile.center_target_frame_recall)} | "
                f"{format_ratio(profile.bbox_target_frame_recall)} |"
            )
        lines.append("")
        return "\n".join(lines)


def default_static_zone_profiles() -> list[StaticZoneProfile]:
    return [
        StaticZoneProfile(name="top_05_center", max_area_ratio=0.05),
        StaticZoneProfile(name="top_10_center", max_area_ratio=0.10),
        StaticZoneProfile(name="top_20_center", max_area_ratio=0.20),
        StaticZoneProfile(name="top_30_center", max_area_ratio=0.30),
        StaticZoneProfile(name="top_10_dilate1", max_area_ratio=0.10, dilation_cells=1),
        StaticZoneProfile(name="top_20_dilate1", max_area_ratio=0.20, dilation_cells=1),
        StaticZoneProfile(name="top_30_dilate1", max_area_ratio=0.30, dilation_cells=1),
    ]


def build_static_zone_prior_report(
    ground_truth: Iterable[GroundTruthAnnotation],
    frame_count: int,
    frame_size: FrameSize,
    grid_shape: GridShape,
    profiles: Iterable[StaticZoneProfile],
    dataset_config: str,
    experiment_name: str,
    target_classes: Iterable[str] | None = None,
) -> tuple[StaticZonePriorReport, list[StaticZoneCellRecord]]:
    gt_records = list(ground_truth)
    gt_by_frame = group_by_frame(gt_records)
    cell_scores = _score_center_cells(gt_records, frame_size, grid_shape)
    selected_by_profile = {
        profile.name: _select_cells(cell_scores, grid_shape, profile)
        for profile in profiles
    }
    profile_reports = {
        profile.name: evaluate_static_zone_profile(
            ground_truth=gt_records,
            gt_by_frame=gt_by_frame,
            frame_size=frame_size,
            grid_shape=grid_shape,
            profile=profile,
            selected_cells=selected_by_profile[profile.name],
        )
        for profile in profiles
    }
    cell_records = _build_cell_records(cell_scores, grid_shape, selected_by_profile)
    report = StaticZonePriorReport(
        dataset_config=dataset_config,
        experiment_name=experiment_name,
        target_classes=tuple(target_classes or ()),
        frame_count=frame_count,
        frame_size=frame_size,
        grid_shape=grid_shape,
        target_gt_count=len(gt_records),
        target_frame_count=len(gt_by_frame),
        occupied_cell_count=sum(1 for count in cell_scores.values() if count > 0),
        profiles=profile_reports,
    )
    return report, cell_records


def evaluate_static_zone_profile(
    ground_truth: list[GroundTruthAnnotation],
    gt_by_frame: dict[tuple[str, int], list[GroundTruthAnnotation]],
    frame_size: FrameSize,
    grid_shape: GridShape,
    profile: StaticZoneProfile,
    selected_cells: set[tuple[int, int]],
) -> StaticZoneProfileReport:
    center_contained_gt_count = 0
    bbox_contained_gt_count = 0
    center_frames: set[tuple[str, int]] = set()
    bbox_frames: set[tuple[str, int]] = set()
    for gt in ground_truth:
        key = (gt.camera_id, gt.frame_id)
        center_cell = _center_cell(gt.bbox_xyxy, frame_size, grid_shape)
        if center_cell in selected_cells:
            center_contained_gt_count += 1
            center_frames.add(key)
        bbox_cells = _bbox_cells(gt.bbox_xyxy, frame_size, grid_shape)
        if bbox_cells and bbox_cells.issubset(selected_cells):
            bbox_contained_gt_count += 1
            bbox_frames.add(key)

    return StaticZoneProfileReport(
        profile=profile,
        selected_cell_count=len(selected_cells),
        selected_area_ratio=(len(selected_cells) / grid_shape.cell_count if grid_shape.cell_count else 0.0),
        target_gt_count=len(ground_truth),
        center_contained_gt_count=center_contained_gt_count,
        bbox_contained_gt_count=bbox_contained_gt_count,
        target_frame_count=len(gt_by_frame),
        center_contained_target_frame_count=len(center_frames),
        bbox_contained_target_frame_count=len(bbox_frames),
    )


def write_static_zone_prior_report_json(report: StaticZonePriorReport, output_path: str | Path) -> None:
    write_json(report.to_json_dict(), output_path)


def write_static_zone_prior_report_markdown(report: StaticZonePriorReport, output_path: str | Path) -> None:
    write_text(report.to_markdown(), output_path)


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
    profile: StaticZoneProfile,
) -> set[tuple[int, int]]:
    base_count = max(1, round(grid_shape.cell_count * profile.max_area_ratio))
    ranked_cells = sorted(
        _all_cells(grid_shape),
        key=lambda cell: (-cell_scores.get(cell, 0), cell[0], cell[1]),
    )
    selected = set(ranked_cells[:base_count])
    if profile.dilation_cells <= 0:
        return selected
    return _dilate_cells(selected, grid_shape, profile.dilation_cells)


def _build_cell_records(
    cell_scores: Counter[tuple[int, int]],
    grid_shape: GridShape,
    selected_by_profile: dict[str, set[tuple[int, int]]],
) -> list[StaticZoneCellRecord]:
    records: list[StaticZoneCellRecord] = []
    for row, column in _all_cells(grid_shape):
        selected_profiles = tuple(
            name
            for name, selected_cells in selected_by_profile.items()
            if (row, column) in selected_cells
        )
        records.append(
            StaticZoneCellRecord(
                row=row,
                column=column,
                center_hit_count=cell_scores.get((row, column), 0),
                selected_profiles=selected_profiles,
            )
        )
    return records


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


def _center_cell(
    bbox_xyxy: list[float],
    frame_size: FrameSize,
    grid_shape: GridShape,
) -> tuple[int, int]:
    x1, y1, x2, y2 = bbox_xyxy
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    return _point_cell(center_x, center_y, frame_size, grid_shape)


def _bbox_cells(
    bbox_xyxy: list[float],
    frame_size: FrameSize,
    grid_shape: GridShape,
) -> set[tuple[int, int]]:
    x1, y1, x2, y2 = bbox_xyxy
    left_column = _axis_cell(x1, frame_size.width, grid_shape.columns)
    right_column = _axis_cell(max(x1, x2 - 1), frame_size.width, grid_shape.columns)
    top_row = _axis_cell(y1, frame_size.height, grid_shape.rows)
    bottom_row = _axis_cell(max(y1, y2 - 1), frame_size.height, grid_shape.rows)
    return {
        (row, column)
        for row in range(top_row, bottom_row + 1)
        for column in range(left_column, right_column + 1)
    }


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


def _cell_in_grid(cell: tuple[int, int], grid_shape: GridShape) -> bool:
    row, column = cell
    return 0 <= row < grid_shape.rows and 0 <= column < grid_shape.columns
