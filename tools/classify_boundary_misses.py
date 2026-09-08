"""Classify ROI containment misses using final ROI and true tile trace artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.io import write_jsonl, write_text
from visualization.artifacts import FrameKey, RoiRunArtifacts, load_roi_run
from visualization.frame_selection import count_contained_gt


MISS_TYPES = (
    "margin_insufficient",
    "adjacent_tile_not_selected",
    "signal_missing",
)

FALSE_ROI_TYPES = (
    "partial_target_boundary",
    "empty_frame_noise",
    "low_density_noise",
    "off_target_motion",
)


@dataclass(frozen=True)
class BoundaryMissRecord:
    run_id: str
    camera_id: str
    frame_id: int
    annotation_id: int | str | None
    class_name: str
    bbox_xyxy: list[float]
    miss_type: str
    intersecting_roi_count: int
    selected_overlapping_tile_ids: list[int]
    unselected_overlapping_tile_ids: list[int]
    host_tile_id: int | None
    host_tile_selected: bool | None
    host_tile_motion_density: float | None
    adjacent_selected_tile_ids: list[int]
    minimum_required_margin_pixels: float | None
    minimum_required_margin_ratio: float | None
    max_overlapping_tile_motion_density: float

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FalseRoiRecord:
    run_id: str
    camera_id: str
    frame_id: int
    roi_id: str | None
    roi_xywh: list[int]
    false_roi_type: str
    target_gt_count: int
    intersecting_target_gt_count: int
    selected_overlapping_tile_ids: list[int]
    max_overlapping_selected_tile_motion_density: float
    nearest_target_distance_pixels: float | None

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BoundaryTaxonomyResult:
    records: list[BoundaryMissRecord]
    false_roi_records: list[FalseRoiRecord]
    skipped_full_frame_gt: int


def classify_boundary_misses(
    run: RoiRunArtifacts,
    max_margin_ratio: float = 0.35,
    noise_density_max: float = 0.02,
) -> BoundaryTaxonomyResult:
    if not run.tile_trace_available:
        raise ValueError(
            f"Run {run.run_id} has no true tile trace; boundary taxonomy cannot infer tiles from ROI."
        )
    if not run.tiles_by_frame:
        raise ValueError(
            f"Run {run.run_id} contains no tile records; boundary taxonomy supports tile policies only."
        )
    target_classes = set(run.compatibility_key["target_classes"])
    records: list[BoundaryMissRecord] = []
    false_roi_records: list[FalseRoiRecord] = []
    skipped_full_frame_gt = 0
    for key, all_gt_records in sorted(run.ground_truth_by_frame.items()):
        gt_records = [
            gt for gt in all_gt_records
            if not target_classes or str(gt.get("class_name")) in target_classes
        ]
        frame_record = run.frames_by_frame.get(key, {})
        if frame_record.get("should_run_full_frame"):
            skipped_full_frame_gt += len(gt_records)
            continue
        rois = run.rois_by_frame.get(key, [])
        if count_contained_gt(rois, gt_records) == len(gt_records):
            continue
        tiles = run.tiles_by_frame.get(key, [])
        for gt in gt_records:
            if raw_gt_contained(gt, rois):
                continue
            records.append(
                classify_miss(
                    run_id=run.run_id,
                    key=key,
                    gt=gt,
                    rois=rois,
                    tiles=tiles,
                    max_margin_ratio=max_margin_ratio,
                )
            )
    for key, rois in sorted(run.rois_by_frame.items()):
        frame_record = run.frames_by_frame.get(key, {})
        if frame_record.get("should_run_full_frame"):
            continue
        gt_records = [
            gt for gt in run.ground_truth_by_frame.get(key, [])
            if not target_classes or str(gt.get("class_name")) in target_classes
        ]
        false_roi_records.extend(
            classify_false_rois_for_frame(
                run_id=run.run_id,
                key=key,
                rois=rois,
                gt_records=gt_records,
                tiles=run.tiles_by_frame.get(key, []),
                noise_density_max=noise_density_max,
            )
        )
    return BoundaryTaxonomyResult(
        records=records,
        false_roi_records=false_roi_records,
        skipped_full_frame_gt=skipped_full_frame_gt,
    )


def classify_miss(
    run_id: str,
    key: FrameKey,
    gt: dict[str, Any],
    rois: list[dict[str, Any]],
    tiles: list[dict[str, Any]],
    max_margin_ratio: float,
) -> BoundaryMissRecord:
    bbox = [float(value) for value in gt["bbox_xyxy"]]
    intersecting_rois = [roi for roi in rois if intersection_area(roi_xyxy(roi), bbox) > 0]
    margin_candidates = [
        required_margin(roi_xyxy(roi), bbox)
        for roi in intersecting_rois
    ]
    minimum_margin_pixels: float | None = None
    minimum_margin_ratio: float | None = None
    if margin_candidates:
        minimum_margin_pixels, minimum_margin_ratio = min(
            margin_candidates,
            key=lambda item: item[1],
        )

    overlapping_tiles = [
        tile for tile in tiles
        if intersection_area(tile_xyxy(tile), bbox) > 0
    ]
    selected_tiles = [tile for tile in overlapping_tiles if tile.get("selected")]
    unselected_tiles = [tile for tile in overlapping_tiles if not tile.get("selected")]
    host_tile = find_host_tile(tiles, bbox)
    adjacent_selected_tiles = (
        [
            tile for tile in tiles
            if tile.get("selected") and tiles_are_adjacent(host_tile, tile)
        ]
        if host_tile is not None
        else []
    )

    if host_tile is not None and host_tile.get("selected"):
        miss_type = "margin_insufficient"
    elif (
        host_tile is not None
        and float(host_tile.get("motion_density", 0.0)) > 0.0
        and adjacent_selected_tiles
    ):
        miss_type = "adjacent_tile_not_selected"
    elif minimum_margin_ratio is not None and minimum_margin_ratio <= max_margin_ratio:
        miss_type = "margin_insufficient"
    else:
        miss_type = "signal_missing"

    return BoundaryMissRecord(
        run_id=run_id,
        camera_id=key[0],
        frame_id=key[1],
        annotation_id=gt.get("annotation_id"),
        class_name=str(gt.get("class_name", "")),
        bbox_xyxy=bbox,
        miss_type=miss_type,
        intersecting_roi_count=len(intersecting_rois),
        selected_overlapping_tile_ids=sorted(int(tile["tile_id"]) for tile in selected_tiles),
        unselected_overlapping_tile_ids=sorted(int(tile["tile_id"]) for tile in unselected_tiles),
        host_tile_id=int(host_tile["tile_id"]) if host_tile is not None else None,
        host_tile_selected=bool(host_tile.get("selected")) if host_tile is not None else None,
        host_tile_motion_density=(
            float(host_tile.get("motion_density", 0.0))
            if host_tile is not None
            else None
        ),
        adjacent_selected_tile_ids=sorted(
            int(tile["tile_id"]) for tile in adjacent_selected_tiles
        ),
        minimum_required_margin_pixels=minimum_margin_pixels,
        minimum_required_margin_ratio=minimum_margin_ratio,
        max_overlapping_tile_motion_density=max(
            (float(tile.get("motion_density", 0.0)) for tile in overlapping_tiles),
            default=0.0,
        ),
    )


def classify_false_rois_for_frame(
    run_id: str,
    key: FrameKey,
    rois: list[dict[str, Any]],
    gt_records: list[dict[str, Any]],
    tiles: list[dict[str, Any]],
    noise_density_max: float,
) -> list[FalseRoiRecord]:
    records: list[FalseRoiRecord] = []
    target_bboxes = [[float(value) for value in gt["bbox_xyxy"]] for gt in gt_records]
    for roi in rois:
        roi_bbox = roi_xyxy(roi)
        if any(contains_bbox_xyxy(roi_bbox, bbox) for bbox in target_bboxes):
            continue
        intersecting_targets = [
            bbox for bbox in target_bboxes
            if intersection_area(roi_bbox, bbox) > 0
        ]
        overlapping_selected_tiles = [
            tile for tile in tiles
            if tile.get("selected") and intersection_area(tile_xyxy(tile), roi_bbox) > 0
        ]
        max_density = max(
            (
                float(tile.get("motion_density", 0.0))
                for tile in overlapping_selected_tiles
            ),
            default=0.0,
        )
        if intersecting_targets:
            false_roi_type = "partial_target_boundary"
        elif not target_bboxes:
            false_roi_type = "empty_frame_noise"
        elif max_density <= noise_density_max:
            false_roi_type = "low_density_noise"
        else:
            false_roi_type = "off_target_motion"

        records.append(
            FalseRoiRecord(
                run_id=run_id,
                camera_id=key[0],
                frame_id=key[1],
                roi_id=roi.get("roi_id"),
                roi_xywh=[int(value) for value in roi["roi_xywh"]],
                false_roi_type=false_roi_type,
                target_gt_count=len(target_bboxes),
                intersecting_target_gt_count=len(intersecting_targets),
                selected_overlapping_tile_ids=sorted(
                    int(tile["tile_id"]) for tile in overlapping_selected_tiles
                ),
                max_overlapping_selected_tile_motion_density=max_density,
                nearest_target_distance_pixels=(
                    min(bbox_distance(roi_bbox, bbox) for bbox in target_bboxes)
                    if target_bboxes
                    else None
                ),
            )
        )
    return records


def raw_gt_contained(gt: dict[str, Any], rois: list[dict[str, Any]]) -> bool:
    bbox = gt["bbox_xyxy"]
    return any(
        roi_bbox[0] <= bbox[0]
        and roi_bbox[1] <= bbox[1]
        and roi_bbox[2] >= bbox[2]
        and roi_bbox[3] >= bbox[3]
        for roi_bbox in (roi_xyxy(roi) for roi in rois)
    )


def required_margin(
    roi_bbox: list[float],
    gt_bbox: list[float],
) -> tuple[float, float]:
    left = max(0.0, roi_bbox[0] - gt_bbox[0])
    top = max(0.0, roi_bbox[1] - gt_bbox[1])
    right = max(0.0, gt_bbox[2] - roi_bbox[2])
    bottom = max(0.0, gt_bbox[3] - roi_bbox[3])
    required = max(left, top, right, bottom)
    roi_width = max(1.0, roi_bbox[2] - roi_bbox[0])
    roi_height = max(1.0, roi_bbox[3] - roi_bbox[1])
    return required, required / min(roi_width, roi_height)


def roi_xyxy(record: dict[str, Any]) -> list[float]:
    x, y, width, height = record["roi_xywh"]
    return [float(x), float(y), float(x + width), float(y + height)]


def tile_xyxy(record: dict[str, Any]) -> list[float]:
    x, y, width, height = record["bbox_xywh"]
    return [float(x), float(y), float(x + width), float(y + height)]


def contains_bbox_xyxy(container: list[float], bbox: list[float]) -> bool:
    return (
        container[0] <= bbox[0]
        and container[1] <= bbox[1]
        and container[2] >= bbox[2]
        and container[3] >= bbox[3]
    )


def intersection_area(first: list[float], second: list[float]) -> float:
    width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    return width * height


def bbox_distance(first: list[float], second: list[float]) -> float:
    if intersection_area(first, second) > 0:
        return 0.0
    dx = max(second[0] - first[2], first[0] - second[2], 0.0)
    dy = max(second[1] - first[3], first[1] - second[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


def find_host_tile(
    tiles: list[dict[str, Any]],
    bbox_xyxy: list[float],
) -> dict[str, Any] | None:
    center_x = (bbox_xyxy[0] + bbox_xyxy[2]) / 2.0
    center_y = (bbox_xyxy[1] + bbox_xyxy[3]) / 2.0
    containing = [
        tile for tile in tiles
        if point_in_tile(center_x, center_y, tile)
    ]
    if containing:
        return min(containing, key=lambda tile: int(tile["tile_id"]))
    return max(
        tiles,
        key=lambda tile: intersection_area(tile_xyxy(tile), bbox_xyxy),
        default=None,
    )


def point_in_tile(x: float, y: float, tile: dict[str, Any]) -> bool:
    tile_x, tile_y, width, height = tile["bbox_xywh"]
    return tile_x <= x < tile_x + width and tile_y <= y < tile_y + height


def tiles_are_adjacent(first: dict[str, Any], second: dict[str, Any]) -> bool:
    row_delta = abs(int(first["row"]) - int(second["row"]))
    col_delta = abs(int(first["col"]) - int(second["col"]))
    return row_delta + col_delta == 1


def render_markdown(
    run: RoiRunArtifacts,
    result: BoundaryTaxonomyResult,
) -> str:
    counts = Counter(record.miss_type for record in result.records)
    false_roi_counts = Counter(record.false_roi_type for record in result.false_roi_records)
    lines = [
        "# ROI Failure Taxonomy",
        "",
        f"- Run: `{run.run_id}`",
        f"- Tile trace: `{'available' if run.tile_trace_available else 'unavailable'}`",
        f"- Classified misses: `{len(result.records)}`",
        f"- Classified false ROIs: `{len(result.false_roi_records)}`",
        f"- GT skipped on full-frame/fallback decisions: `{result.skipped_full_frame_gt}`",
        "",
        "## Boundary Miss Summary",
        "",
        "| Type | Count |",
        "|---|---:|",
    ]
    for miss_type in MISS_TYPES:
        lines.append(f"| `{miss_type}` | {counts[miss_type]} |")
    lines.extend([
        "",
        "## Representative Records",
        "",
        "Up to 20 records per type are shown. The JSONL contains the complete result.",
        "",
        "| Camera | Frame | Annotation | Type | Required margin ratio | Selected tiles | Unselected tiles |",
        "|---|---:|---:|---|---:|---|---|",
    ])
    for miss_type in MISS_TYPES:
        examples = [record for record in result.records if record.miss_type == miss_type][:20]
        for record in examples:
            margin = (
                f"{record.minimum_required_margin_ratio:.4f}"
                if record.minimum_required_margin_ratio is not None
                else "-"
            )
            lines.append(
                f"| `{record.camera_id}` | {record.frame_id} | {record.annotation_id} | "
                f"`{record.miss_type}` | {margin} | "
                f"`{record.selected_overlapping_tile_ids}` | "
                f"`{record.unselected_overlapping_tile_ids}` |"
            )
    lines.append("")
    lines.extend([
        "## False ROI Summary",
        "",
        "| Type | Count |",
        "|---|---:|",
    ])
    for false_roi_type in FALSE_ROI_TYPES:
        lines.append(f"| `{false_roi_type}` | {false_roi_counts[false_roi_type]} |")
    lines.extend([
        "",
        "## Representative False ROIs",
        "",
        "Up to 20 records per type are shown. The JSONL contains the complete result.",
        "",
        "| Camera | Frame | ROI | Type | Max selected tile density | Nearest target px | Selected tiles |",
        "|---|---:|---|---|---:|---:|---|",
    ])
    for false_roi_type in FALSE_ROI_TYPES:
        examples = [
            record for record in result.false_roi_records
            if record.false_roi_type == false_roi_type
        ][:20]
        for record in examples:
            nearest = (
                f"{record.nearest_target_distance_pixels:.1f}"
                if record.nearest_target_distance_pixels is not None
                else "-"
            )
            lines.append(
                f"| `{record.camera_id}` | {record.frame_id} | `{record.roi_id or '-'}` | "
                f"`{record.false_roi_type}` | "
                f"{record.max_overlapping_selected_tile_motion_density:.4f} | "
                f"{nearest} | `{record.selected_overlapping_tile_ids}` |"
            )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify ROI boundary misses from a saved run.")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output-jsonl", default=None)
    parser.add_argument("--output-false-roi-jsonl", default=None)
    parser.add_argument("--output-markdown", default=None)
    parser.add_argument("--max-margin-ratio", type=float, default=0.35)
    parser.add_argument("--noise-density-max", type=float, default=0.02)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run = load_roi_run(args.run_root)
    result = classify_boundary_misses(
        run,
        max_margin_ratio=args.max_margin_ratio,
        noise_density_max=args.noise_density_max,
    )
    output_jsonl = Path(args.output_jsonl) if args.output_jsonl else Path(args.run_root) / "reports" / "boundary_misses.jsonl"
    output_false_roi_jsonl = (
        Path(args.output_false_roi_jsonl)
        if args.output_false_roi_jsonl
        else Path(args.run_root) / "reports" / "false_rois.jsonl"
    )
    output_markdown = (
        Path(args.output_markdown)
        if args.output_markdown
        else Path(args.run_root) / "reports" / "boundary_misses.md"
    )
    write_jsonl(result.records, output_jsonl)
    write_jsonl(result.false_roi_records, output_false_roi_jsonl)
    write_text(render_markdown(run, result), output_markdown)
    print(
        json.dumps(
            {
                "run_id": run.run_id,
                "classified_misses": len(result.records),
                "classified_false_rois": len(result.false_roi_records),
                "output_jsonl": str(output_jsonl),
                "output_false_roi_jsonl": str(output_false_roi_jsonl),
                "output_markdown": str(output_markdown),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
