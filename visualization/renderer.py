"""Render ROI overlays, detection comparisons, and failure cases."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from common import Detection, FramePacket, GroundTruthAnnotation, ROIMetadata
from evaluation.detection_metrics import bbox_iou


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

    rois_by_frame = _group_by_frame(roi_records)
    full_detections_by_frame = _group_by_frame(full_frame_detections)
    roi_detections_by_frame = _group_by_frame(roi_detections)
    gt_by_frame = _group_by_frame(ground_truth or [])
    summary = VisualizationSummary()

    for packet in frames:
        key = _frame_key(packet.camera_id, packet.frame_id)
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
        _draw_detection(cv2, canvas, detection, color=(0, 190, 255), label_prefix="roi")
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
        _draw_detection(cv2, full_panel, detection, color=(255, 160, 0), label_prefix="full")
    for roi_record in rois:
        _draw_roi(cv2, roi_panel, roi_record)
    for detection in roi_detections:
        color = (0, 190, 255) if detection.roi_id else (190, 90, 255)
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
    canvas = draw_detection_comparison(
        cv2,
        np,
        frame,
        rois,
        full_frame_detections,
        roi_detections,
        ground_truth,
    )
    width = frame.shape[1]
    for detection in missed_detections:
        _draw_detection(cv2, canvas, detection, color=(0, 0, 255), label_prefix="missed")
    for gt in missed_gt or []:
        _draw_ground_truth(cv2, canvas, gt, color=(0, 0, 255), label_prefix="missed_gt")
    cv2.putText(
        canvas,
        f"Failure candidates: {len(missed_detections)} pseudo miss, {len(missed_gt or [])} GT miss",
        (width + 12, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )
    return canvas


def find_missed_ground_truth_annotations(
    ground_truth: Iterable[GroundTruthAnnotation],
    candidate_detections: Iterable[Detection],
    iou_threshold: float = 0.5,
) -> list[GroundTruthAnnotation]:
    candidates = list(candidate_detections)
    used_candidate_indexes: set[int] = set()
    missed: list[GroundTruthAnnotation] = []

    for gt in ground_truth:
        best_index = None
        best_iou = 0.0
        for index, candidate in enumerate(candidates):
            if index in used_candidate_indexes:
                continue
            if not _is_gt_match_candidate(gt, candidate):
                continue
            iou = bbox_iou(gt.bbox_xyxy, candidate.bbox_xyxy)
            if iou > best_iou:
                best_iou = iou
                best_index = index

        if best_index is None or best_iou < iou_threshold:
            missed.append(gt)
        else:
            used_candidate_indexes.add(best_index)

    return missed


def find_missed_reference_detections(
    reference_detections: Iterable[Detection],
    candidate_detections: Iterable[Detection],
    iou_threshold: float = 0.5,
) -> list[Detection]:
    candidates = list(candidate_detections)
    used_candidate_indexes: set[int] = set()
    missed: list[Detection] = []

    for reference in reference_detections:
        best_index = None
        best_iou = 0.0
        for index, candidate in enumerate(candidates):
            if index in used_candidate_indexes:
                continue
            if not _is_match_candidate(reference, candidate):
                continue
            iou = bbox_iou(reference.bbox_xyxy, candidate.bbox_xyxy)
            if iou > best_iou:
                best_iou = iou
                best_index = index

        if best_index is None or best_iou < iou_threshold:
            missed.append(reference)
        else:
            used_candidate_indexes.add(best_index)

    return missed


def _draw_roi(cv2: Any, canvas: Any, roi_record: ROIMetadata) -> None:
    roi = roi_record.roi
    x1, y1, x2, y2 = roi.x, roi.y, roi.x + roi.w, roi.y + roi.h
    cv2.rectangle(canvas, (x1, y1), (x2, y2), (80, 220, 80), 2)
    _draw_label(cv2, canvas, f"ROI {roi_record.roi_id}", x1, y1, (80, 220, 80))


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
    color: tuple[int, int, int] = (255, 0, 255),
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


def _group_by_frame(records: Iterable[Any]) -> dict[tuple[str, int], list[Any]]:
    grouped: dict[tuple[str, int], list[Any]] = {}
    for record in records:
        grouped.setdefault(_frame_key(record.camera_id, record.frame_id), []).append(record)
    return grouped


def _frame_key(camera_id: str, frame_id: int) -> tuple[str, int]:
    return camera_id, frame_id


def _frame_stem(camera_id: str, frame_id: int) -> str:
    safe_camera_id = camera_id.replace("/", "_").replace(" ", "_")
    return f"{safe_camera_id}_f{frame_id:06d}"


def _is_match_candidate(reference: Detection, candidate: Detection) -> bool:
    return (
        reference.camera_id == candidate.camera_id
        and reference.frame_id == candidate.frame_id
        and reference.class_name == candidate.class_name
    )


def _is_gt_match_candidate(gt: GroundTruthAnnotation, candidate: Detection) -> bool:
    return (
        gt.camera_id == candidate.camera_id
        and gt.frame_id == candidate.frame_id
        and _normalize_class_name(gt.class_name) == _normalize_class_name(candidate.class_name)
    )


def _normalize_class_name(class_name: str) -> str:
    normalized = class_name.strip().lower()
    aliases = {
        "bike/bicycle": "bicycle",
        "bike": "bicycle",
        "truck": "vehicle",
        "bus": "vehicle",
    }
    return aliases.get(normalized, normalized)


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
