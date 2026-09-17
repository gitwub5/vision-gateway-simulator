"""Road/lane-like region prior POC metrics for traffic scenes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common import FrameSize, GroundTruthAnnotation
from common.io import write_json, write_text
from common.records import format_ratio, group_by_frame


@dataclass(frozen=True)
class RoadGridShape:
    columns: int
    rows: int

    @property
    def cell_count(self) -> int:
        return self.columns * self.rows

    def to_json_dict(self) -> dict[str, int]:
        return {"columns": self.columns, "rows": self.rows}


@dataclass(frozen=True)
class RoadRegionPriorProfile:
    name: str
    min_row_hit_count: int = 1
    x_margin_cells: int = 0
    y_dilation_cells: int = 0
    bbox_based: bool = True

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RoadRegionCellRecord:
    row: int
    column: int
    hit_count: int
    selected_profiles: tuple[str, ...] = ()

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["selected_profiles"] = list(self.selected_profiles)
        return data


@dataclass(frozen=True)
class RoadRegionPriorProfileReport:
    profile: RoadRegionPriorProfile
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
        return self.center_contained_gt_count / self.target_gt_count if self.target_gt_count else 0.0

    @property
    def bbox_gt_recall(self) -> float:
        return self.bbox_contained_gt_count / self.target_gt_count if self.target_gt_count else 0.0

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
class RoadRegionPriorReport:
    dataset_config: str
    experiment_name: str
    target_classes: tuple[str, ...]
    frame_count: int
    frame_size: FrameSize
    grid_shape: RoadGridShape
    target_gt_count: int
    target_frame_count: int
    occupied_cell_count: int
    profiles: dict[str, RoadRegionPriorProfileReport] = field(default_factory=dict)

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
            "# Road / Lane Region Prior POC Report",
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


def default_road_region_prior_profiles() -> list[RoadRegionPriorProfile]:
    return [
        RoadRegionPriorProfile(name="bbox_envelope_margin_0", x_margin_cells=0, y_dilation_cells=0),
        RoadRegionPriorProfile(name="bbox_envelope_margin_1", x_margin_cells=1, y_dilation_cells=0),
        RoadRegionPriorProfile(name="bbox_envelope_margin_2", x_margin_cells=2, y_dilation_cells=1),
        RoadRegionPriorProfile(name="bbox_envelope_margin_3", x_margin_cells=3, y_dilation_cells=1),
        RoadRegionPriorProfile(name="center_envelope_margin_2", x_margin_cells=2, y_dilation_cells=1, bbox_based=False),
    ]


def build_road_region_prior_report(
    ground_truth: Iterable[GroundTruthAnnotation],
    frame_count: int,
    frame_size: FrameSize,
    grid_shape: RoadGridShape,
    profiles: Iterable[RoadRegionPriorProfile],
    dataset_config: str,
    experiment_name: str,
    target_classes: Iterable[str] | None = None,
) -> tuple[RoadRegionPriorReport, list[RoadRegionCellRecord]]:
    gt_records = list(ground_truth)
    gt_by_frame = group_by_frame(gt_records)
    occupied_cells = _score_bbox_cells(gt_records, frame_size, grid_shape)
    selected_by_profile = {
        profile.name: _select_road_region_cells(gt_records, frame_size, grid_shape, profile)
        for profile in profiles
    }
    profile_reports = {
        profile.name: evaluate_road_region_prior_profile(
            ground_truth=gt_records,
            gt_by_frame=gt_by_frame,
            frame_size=frame_size,
            grid_shape=grid_shape,
            profile=profile,
            selected_cells=selected_by_profile[profile.name],
        )
        for profile in profiles
    }
    cell_records = _build_cell_records(occupied_cells, grid_shape, selected_by_profile)
    report = RoadRegionPriorReport(
        dataset_config=dataset_config,
        experiment_name=experiment_name,
        target_classes=tuple(target_classes or ()),
        frame_count=frame_count,
        frame_size=frame_size,
        grid_shape=grid_shape,
        target_gt_count=len(gt_records),
        target_frame_count=len(gt_by_frame),
        occupied_cell_count=sum(1 for count in occupied_cells.values() if count > 0),
        profiles=profile_reports,
    )
    return report, cell_records


def evaluate_road_region_prior_profile(
    ground_truth: list[GroundTruthAnnotation],
    gt_by_frame: dict[tuple[str, int], list[GroundTruthAnnotation]],
    frame_size: FrameSize,
    grid_shape: RoadGridShape,
    profile: RoadRegionPriorProfile,
    selected_cells: set[tuple[int, int]],
) -> RoadRegionPriorProfileReport:
    center_count = 0
    bbox_count = 0
    center_frames: set[tuple[str, int]] = set()
    bbox_frames: set[tuple[str, int]] = set()
    for gt in ground_truth:
        key = (gt.camera_id, gt.frame_id)
        if _center_cell(gt.bbox_xyxy, frame_size, grid_shape) in selected_cells:
            center_count += 1
            center_frames.add(key)
        bbox_cells = _bbox_cells(gt.bbox_xyxy, frame_size, grid_shape)
        if bbox_cells and bbox_cells.issubset(selected_cells):
            bbox_count += 1
            bbox_frames.add(key)

    return RoadRegionPriorProfileReport(
        profile=profile,
        selected_cell_count=len(selected_cells),
        selected_area_ratio=(len(selected_cells) / grid_shape.cell_count if grid_shape.cell_count else 0.0),
        target_gt_count=len(ground_truth),
        center_contained_gt_count=center_count,
        bbox_contained_gt_count=bbox_count,
        target_frame_count=len(gt_by_frame),
        center_contained_target_frame_count=len(center_frames),
        bbox_contained_target_frame_count=len(bbox_frames),
    )


def write_road_region_prior_report_json(report: RoadRegionPriorReport, output_path: str | Path) -> None:
    write_json(report.to_json_dict(), output_path)


def write_road_region_prior_report_markdown(report: RoadRegionPriorReport, output_path: str | Path) -> None:
    write_text(report.to_markdown(), output_path)


def _select_road_region_cells(
    ground_truth: list[GroundTruthAnnotation],
    frame_size: FrameSize,
    grid_shape: RoadGridShape,
    profile: RoadRegionPriorProfile,
) -> set[tuple[int, int]]:
    row_columns: dict[int, list[int]] = defaultdict(list)
    for gt in ground_truth:
        cells = (
            _bbox_cells(gt.bbox_xyxy, frame_size, grid_shape)
            if profile.bbox_based
            else {_center_cell(gt.bbox_xyxy, frame_size, grid_shape)}
        )
        for row, column in cells:
            row_columns[row].append(column)

    selected: set[tuple[int, int]] = set()
    for row, columns in row_columns.items():
        if len(columns) < profile.min_row_hit_count:
            continue
        start = max(0, min(columns) - profile.x_margin_cells)
        end = min(grid_shape.columns - 1, max(columns) + profile.x_margin_cells)
        for selected_row in range(
            max(0, row - profile.y_dilation_cells),
            min(grid_shape.rows - 1, row + profile.y_dilation_cells) + 1,
        ):
            for column in range(start, end + 1):
                selected.add((selected_row, column))
    return selected


def _score_bbox_cells(
    ground_truth: list[GroundTruthAnnotation],
    frame_size: FrameSize,
    grid_shape: RoadGridShape,
) -> dict[tuple[int, int], int]:
    scores: dict[tuple[int, int], int] = defaultdict(int)
    for gt in ground_truth:
        for cell in _bbox_cells(gt.bbox_xyxy, frame_size, grid_shape):
            scores[cell] += 1
    return dict(scores)


def _build_cell_records(
    hit_counts: dict[tuple[int, int], int],
    grid_shape: RoadGridShape,
    selected_by_profile: dict[str, set[tuple[int, int]]],
) -> list[RoadRegionCellRecord]:
    records: list[RoadRegionCellRecord] = []
    for row in range(grid_shape.rows):
        for column in range(grid_shape.columns):
            cell = (row, column)
            selected_profiles = tuple(
                name for name, cells in selected_by_profile.items() if cell in cells
            )
            records.append(
                RoadRegionCellRecord(
                    row=row,
                    column=column,
                    hit_count=hit_counts.get(cell, 0),
                    selected_profiles=selected_profiles,
                )
            )
    return records


def _center_cell(
    bbox: list[float],
    frame_size: FrameSize,
    grid_shape: RoadGridShape,
) -> tuple[int, int]:
    center_x = (bbox[0] + bbox[2]) / 2
    center_y = (bbox[1] + bbox[3]) / 2
    return _point_cell(center_x, center_y, frame_size, grid_shape)


def _bbox_cells(
    bbox: list[float],
    frame_size: FrameSize,
    grid_shape: RoadGridShape,
) -> set[tuple[int, int]]:
    x1, y1, x2, y2 = bbox
    left = _clamp_cell(int(x1 / frame_size.width * grid_shape.columns), grid_shape.columns)
    right = _clamp_cell(int(max(x1, x2 - 1) / frame_size.width * grid_shape.columns), grid_shape.columns)
    top = _clamp_cell(int(y1 / frame_size.height * grid_shape.rows), grid_shape.rows)
    bottom = _clamp_cell(int(max(y1, y2 - 1) / frame_size.height * grid_shape.rows), grid_shape.rows)
    return {
        (row, column)
        for row in range(top, bottom + 1)
        for column in range(left, right + 1)
    }


def _point_cell(
    x: float,
    y: float,
    frame_size: FrameSize,
    grid_shape: RoadGridShape,
) -> tuple[int, int]:
    column = _clamp_cell(int(x / frame_size.width * grid_shape.columns), grid_shape.columns)
    row = _clamp_cell(int(y / frame_size.height * grid_shape.rows), grid_shape.rows)
    return row, column


def _clamp_cell(value: int, size: int) -> int:
    return max(0, min(size - 1, value))
