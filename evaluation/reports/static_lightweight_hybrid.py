"""Static zone prior + budgeted lightweight visual priority hybrid validation metrics."""

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
class StaticLightweightFrameScores:
    camera_id: str
    frame_id: int
    frame_index: int
    frame_size: FrameSize
    scores_by_signal: dict[str, tuple[float, ...]]


@dataclass(frozen=True)
class StaticLightweightProfile:
    name: str
    static_max_area_ratio: float
    static_dilation_cells: int
    signal_name: str
    extra_budget_ratio: float
    combined_dilation_cells: int = 0

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StaticLightweightFrameRecord:
    camera_id: str
    frame_id: int
    frame_index: int
    profile_name: str
    selected_cell_count: int
    selected_area_ratio: float
    target_gt_count: int
    center_contained_gt_count: int
    bbox_contained_gt_count: int

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StaticLightweightProfileReport:
    profile: StaticLightweightProfile
    static_selected_area_ratio: float
    frame_count: int
    selected_area_ratio: float
    target_gt_count: int
    center_contained_gt_count: int
    bbox_contained_gt_count: int
    static_only_bbox_contained_gt_count: int
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
    def static_only_bbox_gt_recall(self) -> float:
        if self.target_gt_count == 0:
            return 0.0
        return self.static_only_bbox_contained_gt_count / self.target_gt_count

    @property
    def incremental_bbox_gt_recall(self) -> float:
        return self.bbox_gt_recall - self.static_only_bbox_gt_recall

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
        data["static_only_bbox_gt_recall"] = self.static_only_bbox_gt_recall
        data["incremental_bbox_gt_recall"] = self.incremental_bbox_gt_recall
        data["center_target_frame_recall"] = self.center_target_frame_recall
        data["bbox_target_frame_recall"] = self.bbox_target_frame_recall
        return data


@dataclass(frozen=True)
class StaticLightweightReport:
    dataset_config: str
    experiment_name: str
    target_classes: tuple[str, ...]
    frame_count: int
    target_gt_count: int
    target_frame_count: int
    grid_shape: GridShape
    profiles: dict[str, StaticLightweightProfileReport] = field(default_factory=dict)

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
            "# Static Zone Prior + Lightweight Visual Priority Hybrid Report",
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
                "| Profile | Signal | Static area | Combined area | Area reduction | "
                "Center GT recall | BBox GT recall | Static-only BBox recall | Incremental BBox recall |"
            ),
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for profile in self.profiles.values():
            lines.append(
                "| "
                f"`{profile.profile.name}` | "
                f"`{profile.profile.signal_name}` | "
                f"{format_ratio(profile.static_selected_area_ratio)} | "
                f"{format_ratio(profile.selected_area_ratio)} | "
                f"{format_ratio(profile.input_area_reduction)} | "
                f"{format_ratio(profile.center_gt_recall)} | "
                f"{format_ratio(profile.bbox_gt_recall)} | "
                f"{format_ratio(profile.static_only_bbox_gt_recall)} | "
                f"{format_ratio(profile.incremental_bbox_gt_recall)} |"
            )
        lines.append("")
        return "\n".join(lines)


def default_static_lightweight_profiles() -> list[StaticLightweightProfile]:
    return [
        StaticLightweightProfile(
            name="static10_static_only",
            static_max_area_ratio=0.10,
            static_dilation_cells=0,
            signal_name="hybrid",
            extra_budget_ratio=0.0,
            combined_dilation_cells=0,
        ),
        StaticLightweightProfile(
            name="static10_hybrid_budget10",
            static_max_area_ratio=0.10,
            static_dilation_cells=0,
            signal_name="hybrid",
            extra_budget_ratio=0.10,
            combined_dilation_cells=0,
        ),
        StaticLightweightProfile(
            name="static10_hybrid_budget10_dilate1",
            static_max_area_ratio=0.10,
            static_dilation_cells=0,
            signal_name="hybrid",
            extra_budget_ratio=0.10,
            combined_dilation_cells=1,
        ),
        StaticLightweightProfile(
            name="static20_hybrid_budget10_dilate1",
            static_max_area_ratio=0.20,
            static_dilation_cells=0,
            signal_name="hybrid",
            extra_budget_ratio=0.10,
            combined_dilation_cells=1,
        ),
        StaticLightweightProfile(
            name="static10_edge_budget10_dilate1",
            static_max_area_ratio=0.10,
            static_dilation_cells=0,
            signal_name="edge",
            extra_budget_ratio=0.10,
            combined_dilation_cells=1,
        ),
        StaticLightweightProfile(
            name="static10_texture_budget10_dilate1",
            static_max_area_ratio=0.10,
            static_dilation_cells=0,
            signal_name="texture",
            extra_budget_ratio=0.10,
            combined_dilation_cells=1,
        ),
    ]


def build_static_lightweight_report(
    frame_scores: Iterable[StaticLightweightFrameScores],
    ground_truth: Iterable[GroundTruthAnnotation],
    profiles: Iterable[StaticLightweightProfile],
    grid_shape: GridShape,
    frame_size: FrameSize,
    dataset_config: str,
    experiment_name: str,
    target_classes: Iterable[str] | None = None,
) -> tuple[StaticLightweightReport, list[StaticLightweightFrameRecord]]:
    frame_records = list(frame_scores)
    gt_records = list(ground_truth)
    gt_by_frame = group_by_frame(gt_records)
    cell_scores = _score_center_cells(gt_records, frame_size, grid_shape)
    profile_reports: dict[str, StaticLightweightProfileReport] = {}
    all_records: list[StaticLightweightFrameRecord] = []
    for profile in profiles:
        static_cells = _select_cells(
            cell_scores, grid_shape, profile.static_max_area_ratio, profile.static_dilation_cells
        )
        report, records = evaluate_static_lightweight_profile(
            frame_records, gt_by_frame, static_cells, grid_shape, profile
        )
        profile_reports[profile.name] = report
        all_records.extend(records)
    return (
        StaticLightweightReport(
            dataset_config=dataset_config,
            experiment_name=experiment_name,
            target_classes=tuple(target_classes or ()),
            frame_count=len(frame_records),
            target_gt_count=len(gt_records),
            target_frame_count=len(gt_by_frame),
            grid_shape=grid_shape,
            profiles=profile_reports,
        ),
        all_records,
    )


def evaluate_static_lightweight_profile(
    frame_scores: list[StaticLightweightFrameScores],
    gt_by_frame: dict[tuple[str, int], list[GroundTruthAnnotation]],
    static_selected_cells: set[tuple[int, int]],
    grid_shape: GridShape,
    profile: StaticLightweightProfile,
) -> tuple[StaticLightweightProfileReport, list[StaticLightweightFrameRecord]]:
    records: list[StaticLightweightFrameRecord] = []
    static_area_ratio = len(static_selected_cells) / grid_shape.cell_count if grid_shape.cell_count else 0.0
    extra_budget_count = max(0, round(grid_shape.cell_count * profile.extra_budget_ratio))
    total_selected_ratio = 0.0
    center_contained_gt_count = 0
    bbox_contained_gt_count = 0
    static_only_bbox_contained_gt_count = 0
    target_gt_count = 0
    center_frames: set[tuple[str, int]] = set()
    bbox_frames: set[tuple[str, int]] = set()
    target_frames: set[tuple[str, int]] = set()

    for frame in frame_scores:
        try:
            scores = frame.scores_by_signal[profile.signal_name]
        except KeyError as exc:
            raise ValueError(f"Frame scores do not include signal: {profile.signal_name}") from exc

        selected_cells = _select_budgeted_cells(scores, static_selected_cells, grid_shape, extra_budget_count)
        if profile.combined_dilation_cells > 0:
            selected_cells = _dilate_cells(selected_cells, grid_shape, profile.combined_dilation_cells)
        selected_ratio = len(selected_cells) / grid_shape.cell_count if grid_shape.cell_count else 0.0
        total_selected_ratio += selected_ratio

        gt_records = gt_by_frame.get((frame.camera_id, frame.frame_id), [])
        key = (frame.camera_id, frame.frame_id)
        frame_center_count = 0
        frame_bbox_count = 0
        if gt_records:
            target_frames.add(key)
        for gt in gt_records:
            target_gt_count += 1
            if _center_cell(gt.bbox_xyxy, frame.frame_size, grid_shape) in selected_cells:
                center_contained_gt_count += 1
                frame_center_count += 1
                center_frames.add(key)
            bbox_cells = _bbox_cells(gt.bbox_xyxy, frame.frame_size, grid_shape)
            if bbox_cells and bbox_cells.issubset(selected_cells):
                bbox_contained_gt_count += 1
                frame_bbox_count += 1
                bbox_frames.add(key)
            if bbox_cells and bbox_cells.issubset(static_selected_cells):
                static_only_bbox_contained_gt_count += 1
        records.append(
            StaticLightweightFrameRecord(
                camera_id=frame.camera_id,
                frame_id=frame.frame_id,
                frame_index=frame.frame_index,
                profile_name=profile.name,
                selected_cell_count=len(selected_cells),
                selected_area_ratio=selected_ratio,
                target_gt_count=len(gt_records),
                center_contained_gt_count=frame_center_count,
                bbox_contained_gt_count=frame_bbox_count,
            )
        )

    report = StaticLightweightProfileReport(
        profile=profile,
        static_selected_area_ratio=static_area_ratio,
        frame_count=len(frame_scores),
        selected_area_ratio=(total_selected_ratio / len(frame_scores) if frame_scores else 0.0),
        target_gt_count=target_gt_count,
        center_contained_gt_count=center_contained_gt_count,
        bbox_contained_gt_count=bbox_contained_gt_count,
        static_only_bbox_contained_gt_count=static_only_bbox_contained_gt_count,
        target_frame_count=len(target_frames),
        center_contained_target_frame_count=len(center_frames),
        bbox_contained_target_frame_count=len(bbox_frames),
    )
    return report, records


def write_static_lightweight_report_json(report: StaticLightweightReport, output_path: str | Path) -> None:
    write_json(report.to_json_dict(), output_path)


def write_static_lightweight_report_markdown(report: StaticLightweightReport, output_path: str | Path) -> None:
    write_text(report.to_markdown(), output_path)


def _select_budgeted_cells(
    scores: tuple[float, ...],
    static_selected_cells: set[tuple[int, int]],
    grid_shape: GridShape,
    extra_budget_count: int,
) -> set[tuple[int, int]]:
    if extra_budget_count <= 0:
        return set(static_selected_cells)
    remaining = [
        (index, score)
        for index, score in enumerate(scores)
        if _index_to_cell(index, grid_shape) not in static_selected_cells
    ]
    ranked_remaining = sorted(remaining, key=lambda item: (-item[1], item[0]))
    extra_cells = {_index_to_cell(index, grid_shape) for index, _ in ranked_remaining[:extra_budget_count]}
    return static_selected_cells | extra_cells


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
    return _point_cell((x1 + x2) / 2.0, (y1 + y2) / 2.0, frame_size, grid_shape)


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
    return (
        _axis_cell(y, frame_size.height, grid_shape.rows),
        _axis_cell(x, frame_size.width, grid_shape.columns),
    )


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


def _index_to_cell(index: int, grid_shape: GridShape) -> tuple[int, int]:
    return index // grid_shape.columns, index % grid_shape.columns


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
