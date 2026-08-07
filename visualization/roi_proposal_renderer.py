"""Render target-aware ROI proposal failure visualizations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from common import FramePacket, GateFrameMetadata, GroundTruthAnnotation, ROIMetadata
from evaluation.class_filter import filter_gt_by_target_classes
from evaluation.roi_containment import contains_bbox


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
    for path in directory.glob("*.jpg"):
        if path.is_file():
            path.unlink()


def load_visualization_dependencies():
    try:
        import cv2
        import numpy as np
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "OpenCV and NumPy are required for ROI proposal visualization rendering. "
            "Install project dependencies with `pip install -r requirements.txt`."
        ) from exc
    return cv2, np


def frame_stem(packet: FramePacket) -> str:
    safe_camera_id = packet.camera_id.replace("/", "_").replace(" ", "_")
    return f"{safe_camera_id}_f{packet.frame_id:06d}"
