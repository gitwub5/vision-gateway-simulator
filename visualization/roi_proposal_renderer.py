"""Render target-aware ROI proposal failure visualizations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from common import FramePacket, GateFrameMetadata, GroundTruthAnnotation, ROIMetadata
from common.io import write_json
from common.records import frame_key
from evaluation.metrics.class_filter import filter_gt_by_target_classes
from evaluation.metrics.roi_containment import contains_bbox
from visualization.artifacts import FrameKey, RoiRunArtifacts
from visualization.frame_selection import review_failure_reasons, select_review_frame_keys
from visualization.primitives import (
    COLOR_ROI,
    COLOR_TILE,
    clear_images,
    draw_gt_record,
    draw_roi_record,
    draw_title as draw_shared_title,
    draw_xyxy,
    frame_stem as shared_frame_stem,
    load_visualization_dependencies as load_shared_dependencies,
)


REVIEW_VIEWS = ("overlay", "containment", "failures")
REVIEW_SUBDIRECTORIES = {
    "overlay": "roi_overlay",
    "containment": "containment",
    "failures": "failures",
}


@dataclass
class RoiRunReviewSummary:
    source_run_id: str
    selection_preset: str
    tile_trace_available: bool
    selected_frames: list[list[Any]]
    rendered_by_view: dict[str, int]
    output_root: str

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


def render_roi_run_review(
    run: RoiRunArtifacts,
    frames: Iterable[FramePacket],
    output_root: str | Path,
    views: tuple[str, ...] = REVIEW_VIEWS,
    selection_preset: str = "missed",
    max_frames: int = 80,
    explicit_frames: Iterable[FrameKey] = (),
) -> RoiRunReviewSummary:
    unknown_views = set(views) - set(REVIEW_VIEWS)
    if unknown_views:
        raise ValueError(f"Unsupported review views: {sorted(unknown_views)}")
    cv2, _ = load_shared_dependencies()
    root = Path(output_root)
    output_dirs = {view: root / REVIEW_SUBDIRECTORIES[view] for view in views}
    for directory in output_dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
        clear_images(directory)

    selected = select_review_frame_keys(
        run,
        preset=selection_preset,
        max_frames=max_frames,
        explicit=explicit_frames,
    )
    selected_set = set(selected)
    rendered = {view: 0 for view in views}
    for packet in frames:
        key = frame_key(packet.camera_id, packet.frame_id)
        if key not in selected_set:
            continue
        rois = run.rois_by_frame.get(key, [])
        tiles = run.tiles_by_frame.get(key, [])
        gt_records = run.ground_truth_by_frame.get(key, [])
        stem = shared_frame_stem(packet.camera_id, packet.frame_id)
        if "overlay" in output_dirs:
            image = draw_run_overlay(cv2, packet.frame, rois, tiles, gt_records, run.tile_trace_available)
            cv2.imwrite(str(output_dirs["overlay"] / f"{stem}_roi_overlay.jpg"), image)
            rendered["overlay"] += 1
        if "containment" in output_dirs:
            image = draw_run_containment(cv2, packet.frame, rois, gt_records)
            cv2.imwrite(str(output_dirs["containment"] / f"{stem}_containment.jpg"), image)
            rendered["containment"] += 1
        failure_reasons = review_failure_reasons(run, key)
        if "failures" in output_dirs and failure_reasons:
            image = draw_run_containment(
                cv2,
                packet.frame,
                rois,
                gt_records,
                title=f"ROI Failure: {', '.join(failure_reasons)}",
            )
            cv2.imwrite(str(output_dirs["failures"] / f"{stem}_failure.jpg"), image)
            rendered["failures"] += 1

    summary = RoiRunReviewSummary(
        source_run_id=run.run_id,
        selection_preset=selection_preset,
        tile_trace_available=run.tile_trace_available,
        selected_frames=[[camera_id, frame_id] for camera_id, frame_id in selected],
        rendered_by_view=rendered,
        output_root=str(root),
    )
    write_json(summary.to_json_dict(), root / "manifest.json")
    return summary


def draw_run_overlay(
    cv2: Any,
    frame: Any,
    rois: list[dict[str, Any]],
    tiles: list[dict[str, Any]],
    gt_records: list[dict[str, Any]],
    tile_trace_available: bool,
) -> Any:
    canvas = frame.copy()
    draw_shared_title(
        cv2,
        canvas,
        "Final ROI + GT" + ("" if tile_trace_available else " (tile trace unavailable)"),
    )
    if tile_trace_available:
        for tile in tiles:
            if tile.get("selected"):
                x, y, width, height = tile["bbox_xywh"]
                draw_xyxy(cv2, canvas, [x, y, x + width, y + height], COLOR_TILE, "")
    for roi in rois:
        draw_roi_record(cv2, canvas, roi, COLOR_ROI, "ROI")
    for gt in gt_records:
        draw_gt_record(cv2, canvas, gt, raw_gt_contained(gt, rois))
    return canvas


def draw_run_containment(
    cv2: Any,
    frame: Any,
    rois: list[dict[str, Any]],
    gt_records: list[dict[str, Any]],
    title: str = "GT Containment",
) -> Any:
    canvas = frame.copy()
    draw_shared_title(cv2, canvas, title)
    for roi in rois:
        draw_roi_record(cv2, canvas, roi, COLOR_ROI, "ROI")
    for gt in gt_records:
        draw_gt_record(cv2, canvas, gt, raw_gt_contained(gt, rois))
    return canvas


def raw_gt_contained(gt_record: dict[str, Any], roi_records: list[dict[str, Any]]) -> bool:
    return any(raw_roi_contains(roi, gt_record["bbox_xyxy"]) for roi in roi_records)


def raw_roi_contains(roi_record: dict[str, Any], bbox_xyxy: list[float]) -> bool:
    x, y, width, height = roi_record["roi_xywh"]

    class RawRoi:
        pass

    roi = RawRoi()
    roi.x, roi.y, roi.w, roi.h = int(x), int(y), int(width), int(height)
    return contains_bbox(roi, bbox_xyxy)


def render_roi_failure_visualizations(
    frames: Iterable[FramePacket],
    roi_records: Iterable[ROIMetadata],
    frame_records: Iterable[GateFrameMetadata],
    ground_truth: Iterable[GroundTruthAnnotation],
    output_dir: str | Path,
    target_classes: tuple[str, ...] = (),
    render_limit: int | None = None,
    roi_too_large_ratio: float = 0.30,
    clear_existing: bool = True,
) -> dict[str, int]:
    cv2, np = load_visualization_dependencies()
    failures_dir = Path(output_dir)
    failures_dir.mkdir(parents=True, exist_ok=True)
    if clear_existing:
        clear_jpgs(failures_dir)

    rois_by_frame = group_by_frame(list(roi_records))
    frames_by_key = {
        (frame.camera_id, frame.frame_id): frame
        for frame in frame_records
    }
    gt_by_frame = group_by_frame(filter_gt_by_target_classes(ground_truth, target_classes))

    processed_frames = 0
    failure_count = 0
    for packet in frames:
        key = (packet.camera_id, packet.frame_id)
        frame_gt = gt_by_frame.get(key, [])
        frame_rois = rois_by_frame.get(key, [])
        frame_record = frames_by_key.get(key)
        reasons = roi_failure_reasons(
            packet=packet,
            rois=frame_rois,
            target_gt=frame_gt,
            frame_record=frame_record,
            roi_too_large_ratio=roi_too_large_ratio,
        )
        if reasons:
            image = draw_roi_failure_case(cv2, np, packet, frame_rois, frame_gt, frame_record, reasons)
            cv2.imwrite(str(failures_dir / f"{frame_stem(packet)}_roi_failure.jpg"), image)
            failure_count += 1
        processed_frames += 1
        if render_limit is not None and processed_frames >= render_limit:
            break
    return {"processed_frames": processed_frames, "failure_case_count": failure_count}


def roi_failure_reasons(
    packet: FramePacket,
    rois: list[ROIMetadata],
    target_gt: list[GroundTruthAnnotation],
    frame_record: GateFrameMetadata | None,
    roi_too_large_ratio: float,
) -> list[str]:
    if not target_gt:
        return []
    reasons: list[str] = []
    total_roi_area = sum(roi_record.roi.area() for roi_record in rois)
    frame_area = packet.original_size.area()
    missed_gt = [
        gt for gt in target_gt if not any(contains_bbox(roi_record.roi, gt.bbox_xyxy) for roi_record in rois)
    ]
    if not rois:
        reasons.append("no_roi_for_target_frame")
    if missed_gt:
        reasons.append("target_gt_out_roi")
    if frame_area > 0 and total_roi_area / frame_area > roi_too_large_ratio:
        reasons.append("roi_too_large")
    if frame_record and frame_record.should_run_full_frame:
        reasons.append("full_frame_check_for_target_frame")
    return reasons


def draw_roi_failure_case(
    cv2: Any,
    np: Any,
    packet: FramePacket,
    rois: list[ROIMetadata],
    target_gt: list[GroundTruthAnnotation],
    frame_record: GateFrameMetadata | None,
    reasons: list[str],
) -> Any:
    reference_panel = packet.frame.copy()
    roi_panel = packet.frame.copy()
    containment_panel = packet.frame.copy()
    summary_panel = blank_panel(cv2, packet, "ROI Proposal Failure Summary")
    draw_title(cv2, reference_panel, "Target GT")
    draw_title(cv2, roi_panel, "ROI Proposal")
    draw_title(cv2, containment_panel, "Target Containment")

    for gt in target_gt:
        draw_gt(cv2, reference_panel, gt, color=(255, 0, 255), label_prefix="target")
        draw_gt(cv2, roi_panel, gt, color=(255, 0, 255), label_prefix="target")
    for roi_record in rois:
        draw_roi(cv2, roi_panel, roi_record)
        draw_roi(cv2, containment_panel, roi_record)
    for gt in target_gt:
        contained = any(contains_bbox(roi_record.roi, gt.bbox_xyxy) for roi_record in rois)
        color = (255, 0, 255) if contained else (0, 0, 255)
        label = "target_in_roi" if contained else "target_out_roi"
        draw_gt(cv2, containment_panel, gt, color=color, label_prefix=label)

    total_roi_area = sum(roi_record.roi.area() for roi_record in rois)
    frame_area = packet.original_size.area()
    lines = [
        f"frame: {packet.camera_id} #{packet.frame_id}",
        f"reasons: {', '.join(reasons)}",
        f"target_gt: {len(target_gt)}",
        f"roi_count: {len(rois)}",
        f"total_roi_area_ratio: {(total_roi_area / frame_area if frame_area else 0.0):.3f}",
        f"trigger_type: {frame_record.trigger_type if frame_record else 'unknown'}",
        f"full_frame_check: {bool(frame_record and frame_record.should_run_full_frame)}",
    ]
    for index, line in enumerate(lines):
        cv2.putText(
            summary_panel,
            line,
            (12, 58 + index * 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (235, 235, 235),
            1,
            cv2.LINE_AA,
        )
    draw_legend(cv2, summary_panel, start_y=286)

    top = np.concatenate([reference_panel, roi_panel], axis=1)
    bottom = np.concatenate([containment_panel, summary_panel], axis=1)
    return np.concatenate([top, bottom], axis=0)


def draw_roi(cv2: Any, canvas: Any, roi_record: ROIMetadata) -> None:
    roi = roi_record.roi
    x1, y1, x2, y2 = roi.x, roi.y, roi.x + roi.w, roi.y + roi.h
    cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 220, 255), 2)
    draw_label(cv2, canvas, "ROI", x1, y1, (0, 220, 255))


def draw_gt(cv2: Any, canvas: Any, gt: GroundTruthAnnotation, color: tuple[int, int, int], label_prefix: str) -> None:
    x1, y1, x2, y2 = [int(round(value)) for value in gt.bbox_xyxy]
    cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
    draw_label(cv2, canvas, f"{label_prefix}:{gt.class_name}", x1, y2, color)


def draw_label(cv2: Any, canvas: Any, label: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    y = max(16, y)
    cv2.putText(canvas, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)


def draw_title(cv2: Any, canvas: Any, title: str) -> None:
    cv2.rectangle(canvas, (0, 0), (360, 28), (32, 32, 32), -1)
    cv2.putText(canvas, title, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)


def blank_panel(cv2: Any, packet: FramePacket, title: str) -> Any:
    panel = packet.frame.copy()
    cv2.rectangle(panel, (0, 0), (packet.original_size.width, packet.original_size.height), (28, 28, 28), -1)
    draw_title(cv2, panel, title)
    return panel


def draw_legend(cv2: Any, panel: Any, start_y: int) -> None:
    entries = [
        ("ROI", (0, 220, 255)),
        ("Target GT contained", (255, 0, 255)),
        ("Target GT missed by ROI", (0, 0, 255)),
    ]
    for index, (label, color) in enumerate(entries):
        y = start_y + index * 28
        cv2.rectangle(panel, (12, y - 14), (34, y + 6), color, 2)
        cv2.putText(panel, label, (44, y + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (235, 235, 235), 1, cv2.LINE_AA)


def group_by_frame(records):
    grouped = defaultdict(list)
    for record in records:
        grouped[(record.camera_id, record.frame_id)].append(record)
    return dict(grouped)


def clear_jpgs(directory: Path) -> None:
    clear_images(directory, suffixes=(".jpg",))


def load_visualization_dependencies():
    return load_shared_dependencies()


def frame_stem(packet: FramePacket) -> str:
    return shared_frame_stem(packet.camera_id, packet.frame_id)
