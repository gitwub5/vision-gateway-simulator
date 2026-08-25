"""Detection-level comparison metrics."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from common import Detection


@dataclass(frozen=True)
class DetectionMatchSummary:
    reference_detection_count: int
    candidate_detection_count: int
    matched_detection_count: int
    iou_threshold: float

    @property
    def pseudo_recall(self) -> float:
        if self.reference_detection_count == 0:
            return 0.0
        return self.matched_detection_count / self.reference_detection_count

    def to_json_dict(self) -> dict:
        return {
            "reference_detection_count": self.reference_detection_count,
            "candidate_detection_count": self.candidate_detection_count,
            "matched_detection_count": self.matched_detection_count,
            "iou_threshold": self.iou_threshold,
            "pseudo_recall": self.pseudo_recall,
            "recall_retention": recall_retention(1.0, self.pseudo_recall),
        }


def recall_retention(full_frame_recall: float, roi_gated_recall: float) -> float:
    if full_frame_recall == 0:
        return 0.0
    return roi_gated_recall / full_frame_recall


def bbox_iou(left: list[float], right: list[float]) -> float:
    left_x1, left_y1, left_x2, left_y2 = left
    right_x1, right_y1, right_x2, right_y2 = right

    inter_x1 = max(left_x1, right_x1)
    inter_y1 = max(left_y1, right_y1)
    inter_x2 = min(left_x2, right_x2)
    inter_y2 = min(left_y2, right_y2)
    inter_area = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)

    left_area = max(0.0, left_x2 - left_x1) * max(0.0, left_y2 - left_y1)
    right_area = max(0.0, right_x2 - right_x1) * max(0.0, right_y2 - right_y1)
    union_area = left_area + right_area - inter_area
    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def match_detections_by_iou(
    reference_detections: Iterable[Detection],
    candidate_detections: Iterable[Detection],
    iou_threshold: float = 0.5,
) -> DetectionMatchSummary:
    references = list(reference_detections)
    candidates = list(candidate_detections)
    candidates_by_key = _group_by_match_key(candidates)
    matched_candidate_ids: set[int] = set()
    matched_count = 0

    for reference in references:
        key = _match_key(reference)
        best_candidate_id = None
        best_iou = 0.0
        for index, candidate in candidates_by_key.get(key, []):
            if index in matched_candidate_ids:
                continue
            iou = bbox_iou(reference.bbox_xyxy, candidate.bbox_xyxy)
            if iou > best_iou:
                best_iou = iou
                best_candidate_id = index

        if best_candidate_id is not None and best_iou >= iou_threshold:
            matched_candidate_ids.add(best_candidate_id)
            matched_count += 1

    return DetectionMatchSummary(
        reference_detection_count=len(references),
        candidate_detection_count=len(candidates),
        matched_detection_count=matched_count,
        iou_threshold=iou_threshold,
    )


def _group_by_match_key(detections: list[Detection]) -> dict[tuple[str, int, str], list[tuple[int, Detection]]]:
    grouped: dict[tuple[str, int, str], list[tuple[int, Detection]]] = {}
    for index, detection in enumerate(detections):
        grouped.setdefault(_match_key(detection), []).append((index, detection))
    return grouped


def _match_key(detection: Detection) -> tuple[str, int, str]:
    return detection.camera_id, detection.frame_id, detection.class_name
