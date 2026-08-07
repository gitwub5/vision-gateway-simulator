"""Render ROI overlays, detection comparisons, and failure cases."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from common import Detection, FramePacket, GroundTruthAnnotation, ROIMetadata
from common.records import frame_key, group_by_frame
from visualization.matching import (
    find_missed_ground_truth_annotations,
    find_missed_reference_detections,
)


COLOR_ROI = (0, 220, 255)
COLOR_GT = (255, 0, 255)
COLOR_FULL_DETECTION = (255, 128, 0)
COLOR_ROI_DETECTION = (0, 140, 255)
COLOR_FALLBACK_DETECTION = (180, 80, 255)
COLOR_MISSED = (0, 0, 255)


@dataclass
class VisualizationSummary:
    processed_frames: int = 0
    roi_overlay_count: int = 0
    comparison_count: int = 0
    failure_case_count: int = 0

    def to_json_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class VisualizationOutputDirs:
    roi_overlay: Path
    comparison: Path
    failures: Path

    @classmethod
    def from_root(cls, output_root: str | Path) -> "VisualizationOutputDirs":
        root = Path(output_root)
        return cls(
            roi_overlay=root / "roi_overlay",
            comparison=root / "comparison",
            failures=root / "failures",
        )

    def mkdirs(self) -> None:
        self.roi_overlay.mkdir(parents=True, exist_ok=True)
        self.comparison.mkdir(parents=True, exist_ok=True)
        self.failures.mkdir(parents=True, exist_ok=True)


def render_visualizations(
    frames: Iterable[FramePacket],
    roi_records: Iterable[ROIMetadata],
    full_frame_detections: Iterable[Detection],
    roi_detections: Iterable[Detection],
    ground_truth: Iterable[GroundTruthAnnotation] | None = None,
    output_root: str | Path = "outputs/visualizations",
    limit: int | None = None,
    iou_threshold: float = 0.5,
) -> VisualizationSummary:
    cv2, np = _load_dependencies()
    output_dirs = VisualizationOutputDirs.from_root(output_root)
    output_dirs.mkdirs()
    _clear_visualization_outputs(output_dirs)

    rois_by_frame = group_by_frame(roi_records)
    full_detections_by_frame = group_by_frame(full_frame_detections)
    roi_detections_by_frame = group_by_frame(roi_detections)
    gt_by_frame = group_by_frame(ground_truth or [])
    summary = VisualizationSummary()

    for packet in frames:
        key = frame_key(packet.camera_id, packet.frame_id)
        frame_rois = rois_by_frame.get(key, [])
        frame_full_detections = full_detections_by_frame.get(key, [])
        frame_roi_detections = roi_detections_by_frame.get(key, [])
        frame_gt = gt_by_frame.get(key, [])
        summary.processed_frames += 1
        stem = _frame_stem(packet.camera_id, packet.frame_id)

        roi_overlay = draw_roi_overlay(cv2, packet.frame, frame_rois, frame_roi_detections, frame_gt)
        cv2.imwrite(str(output_dirs.roi_overlay / f"{stem}_roi_overlay.jpg"), roi_overlay)
        summary.roi_overlay_count += 1

        comparison = draw_detection_comparison(
            cv2,
            np,
            packet.frame,
            frame_rois,
            frame_full_detections,
            frame_roi_detections,
            frame_gt,
        )
        cv2.imwrite(str(output_dirs.comparison / f"{stem}_comparison.jpg"), comparison)
        summary.comparison_count += 1

        missed = find_missed_reference_detections(
            frame_full_detections,
            frame_roi_detections,
            iou_threshold=iou_threshold,
        )
        missed_gt = find_missed_ground_truth_annotations(
            frame_gt,
            frame_roi_detections,
            iou_threshold=iou_threshold,
        )
        if missed or missed_gt:
            failure = draw_failure_case(
                cv2,
                np,
                packet.frame,
                frame_rois,
                frame_full_detections,
                frame_roi_detections,
                missed,
                frame_gt,
                missed_gt,
            )
            cv2.imwrite(str(output_dirs.failures / f"{stem}_failure.jpg"), failure)
            summary.failure_case_count += 1

        if limit is not None and summary.processed_frames >= limit:
            break

    return summary


def draw_roi_overlay(
    cv2: Any,
    frame: Any,
    rois: list[ROIMetadata],
    detections: list[Detection],
    ground_truth: list[GroundTruthAnnotation] | None = None,
) -> Any:
    canvas = frame.copy()
    for roi_record in rois:
        _draw_roi(cv2, canvas, roi_record)
    for gt in ground_truth or []:
        _draw_ground_truth(cv2, canvas, gt)
    for detection in detections:
        _draw_detection(cv2, canvas, detection, color=COLOR_ROI_DETECTION, label_prefix="roi")
    return canvas


def draw_detection_comparison(
    cv2: Any,
    np: Any,
    frame: Any,
    rois: list[ROIMetadata],
    full_frame_detections: list[Detection],
    roi_detections: list[Detection],
    ground_truth: list[GroundTruthAnnotation] | None = None,
) -> Any:
    full_panel = frame.copy()
    roi_panel = frame.copy()
    _draw_panel_title(cv2, full_panel, "Full-frame YOLO")
    _draw_panel_title(cv2, roi_panel, "ROI-gated YOLO")
    for gt in ground_truth or []:
        _draw_ground_truth(cv2, full_panel, gt)
        _draw_ground_truth(cv2, roi_panel, gt)
    for detection in full_frame_detections:
        _draw_detection(cv2, full_panel, detection, color=COLOR_FULL_DETECTION, label_prefix="full")
    for roi_record in rois:
        _draw_roi(cv2, roi_panel, roi_record)
    for detection in roi_detections:
        color = COLOR_ROI_DETECTION if detection.roi_id else COLOR_FALLBACK_DETECTION
        _draw_detection(cv2, roi_panel, detection, color=color, label_prefix="roi")
    return np.concatenate([full_panel, roi_panel], axis=1)


def draw_failure_case(
    cv2: Any,
    np: Any,
    frame: Any,
    rois: list[ROIMetadata],
    full_frame_detections: list[Detection],
    roi_detections: list[Detection],
    missed_detections: list[Detection],
    ground_truth: list[GroundTruthAnnotation] | None = None,
    missed_gt: list[GroundTruthAnnotation] | None = None,
) -> Any:
    reference_panel = draw_full_frame_detection_panel(
        cv2,
        frame,
        "Reference: Full-frame YOLO + GT",
        full_frame_detections,
        ground_truth,
        missed_detections,
    )
    candidate_panel = draw_roi_gated_detection_panel(
        cv2,
        frame,
        "Candidate: ROI-gated YOLO",
        rois,
        roi_detections,
        ground_truth,
        missed_gt,
    )
    misses_panel = draw_e2e_misses_panel(cv2, frame, missed_detections, missed_gt or [])
    summary_panel = draw_e2e_failure_summary_panel(
        cv2,
        frame,
        full_frame_detections,
        roi_detections,
        missed_detections,
        missed_gt or [],
    )

    top = np.concatenate([reference_panel, candidate_panel], axis=1)
    bottom = np.concatenate([misses_panel, summary_panel], axis=1)
    canvas = np.concatenate([top, bottom], axis=0)

    return canvas


def draw_full_frame_detection_panel(
    cv2: Any,
    frame: Any,
    title: str,
    full_frame_detections: list[Detection],
    ground_truth: list[GroundTruthAnnotation] | None = None,
    missed_detections: list[Detection] | None = None,
) -> Any:
    panel = frame.copy()
    _draw_panel_title(cv2, panel, title)
    for gt in ground_truth or []:
        _draw_ground_truth(cv2, panel, gt)
    for detection in full_frame_detections:
        _draw_detection(cv2, panel, detection, color=COLOR_FULL_DETECTION, label_prefix="full")
    for detection in missed_detections or []:
        _draw_detection(cv2, panel, detection, color=COLOR_MISSED, label_prefix="missed")
    return panel


def draw_roi_gated_detection_panel(
    cv2: Any,
    frame: Any,
    title: str,
    rois: list[ROIMetadata],
    roi_detections: list[Detection],
    ground_truth: list[GroundTruthAnnotation] | None = None,
    missed_gt: list[GroundTruthAnnotation] | None = None,
) -> Any:
    panel = frame.copy()
    _draw_panel_title(cv2, panel, title)
    for gt in ground_truth or []:
        _draw_ground_truth(cv2, panel, gt)
    for roi_record in rois:
        _draw_roi(cv2, panel, roi_record)
    for detection in roi_detections:
        color = COLOR_ROI_DETECTION if detection.roi_id else COLOR_FALLBACK_DETECTION
        _draw_detection(cv2, panel, detection, color=color, label_prefix="roi")
    for gt in missed_gt or []:
        _draw_ground_truth(cv2, panel, gt, color=COLOR_MISSED, label_prefix="missed_gt")
    return panel


def draw_e2e_misses_panel(
    cv2: Any,
    frame: Any,
    missed_detections: list[Detection],
    missed_gt: list[GroundTruthAnnotation],
) -> Any:
    panel = frame.copy()
    _draw_panel_title(cv2, panel, "E2E Misses")
    for detection in missed_detections:
        _draw_detection(cv2, panel, detection, color=COLOR_MISSED, label_prefix="pseudo_miss")
    for gt in missed_gt:
        _draw_ground_truth(cv2, panel, gt, color=COLOR_MISSED, label_prefix="gt_miss")
    return panel


def draw_e2e_failure_summary_panel(
    cv2: Any,
    frame: Any,
    full_frame_detections: list[Detection],
    roi_detections: list[Detection],
    missed_detections: list[Detection],
    missed_gt: list[GroundTruthAnnotation],
) -> Any:
    panel = draw_blank_panel(cv2, frame, "E2E Failure Summary")
    fallback_detection_count = sum(1 for detection in roi_detections if not detection.roi_id)
    lines = [
        f"pseudo_miss: {len(missed_detections)}",
        f"gt_miss: {len(missed_gt)}",
        f"full_detections: {len(full_frame_detections)}",
        f"roi_detections: {len(roi_detections)}",
        f"fallback_detections: {fallback_detection_count}",
        "",
        "failure condition:",
        "pseudo_miss > 0 or gt_miss > 0",
    ]
    for index, line in enumerate(lines):
        if not line:
            continue
        cv2.putText(
            panel,
            line,
            (12, 58 + index * 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (235, 235, 235),
            2,
            cv2.LINE_AA,
        )
    _draw_legend(cv2, panel, start_x=12, start_y=284)
    return panel


def draw_blank_panel(cv2: Any, frame: Any, title: str) -> Any:
    panel = frame.copy()
    cv2.rectangle(panel, (0, 0), (frame.shape[1], frame.shape[0]), (28, 28, 28), -1)
    _draw_panel_title(cv2, panel, title)
    return panel


def _draw_legend(cv2: Any, panel: Any, start_x: int = 12, start_y: int = 58) -> None:
    entries = [
        ("ROI", COLOR_ROI),
        ("GT", COLOR_GT),
        ("Full-frame YOLO", COLOR_FULL_DETECTION),
        ("ROI YOLO", COLOR_ROI_DETECTION),
        ("Fallback YOLO", COLOR_FALLBACK_DETECTION),
        ("E2E miss", COLOR_MISSED),
    ]
    for index, (label, color) in enumerate(entries):
        y = start_y + index * 28
        cv2.rectangle(panel, (start_x, y - 14), (start_x + 22, y + 6), color, 2)
        cv2.putText(
            panel,
            label,
            (start_x + 32, y + 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.56,
            (235, 235, 235),
            1,
            cv2.LINE_AA,
        )


def _clear_visualization_outputs(output_dirs: VisualizationOutputDirs) -> None:
    for directory in (output_dirs.roi_overlay, output_dirs.comparison, output_dirs.failures):
        for path in directory.glob("*.jpg"):
            if path.is_file():
                path.unlink()


def _draw_roi(cv2: Any, canvas: Any, roi_record: ROIMetadata) -> None:
    roi = roi_record.roi
    x1, y1, x2, y2 = roi.x, roi.y, roi.x + roi.w, roi.y + roi.h
    cv2.rectangle(canvas, (x1, y1), (x2, y2), COLOR_ROI, 2)
    _draw_label(cv2, canvas, f"ROI {roi_record.roi_id}", x1, y1, COLOR_ROI)


def _draw_detection(
    cv2: Any,
    canvas: Any,
    detection: Detection,
    color: tuple[int, int, int],
    label_prefix: str,
) -> None:
    x1, y1, x2, y2 = [int(round(value)) for value in detection.bbox_xyxy]
    cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
    label = f"{label_prefix}:{detection.class_name} {detection.confidence:.2f}"
    _draw_label(cv2, canvas, label, x1, y1, color)


def _draw_ground_truth(
    cv2: Any,
    canvas: Any,
    gt: GroundTruthAnnotation,
    color: tuple[int, int, int] = COLOR_GT,
    label_prefix: str = "gt",
) -> None:
    x1, y1, x2, y2 = [int(round(value)) for value in gt.bbox_xyxy]
    cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
    _draw_label(cv2, canvas, f"{label_prefix}:{gt.class_name}", x1, y2, color)


def _draw_label(
    cv2: Any,
    canvas: Any,
    label: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    y = max(16, y)
    cv2.putText(canvas, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)


def _draw_panel_title(cv2: Any, canvas: Any, title: str) -> None:
    cv2.rectangle(canvas, (0, 0), (260, 28), (32, 32, 32), -1)
    cv2.putText(canvas, title, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)


def _frame_stem(camera_id: str, frame_id: int) -> str:
    safe_camera_id = camera_id.replace("/", "_").replace(" ", "_")
    return f"{safe_camera_id}_f{frame_id:06d}"


def _load_dependencies():
    try:
        import cv2
        import numpy as np
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "OpenCV and NumPy are required for visualization rendering. "
            "Install dependencies with `pip install -r requirements.txt`."
        ) from exc
    return cv2, np
