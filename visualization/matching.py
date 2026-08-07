"""Matching helpers for visualization failure rendering."""

from __future__ import annotations

from collections.abc import Iterable

from common import Detection, GroundTruthAnnotation
from evaluation.class_filter import normalize_class_name
from evaluation.detection_metrics import bbox_iou


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
            if not is_gt_match_candidate(gt, candidate):
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
            if not is_detection_match_candidate(reference, candidate):
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


def is_detection_match_candidate(reference: Detection, candidate: Detection) -> bool:
    return (
        reference.camera_id == candidate.camera_id
        and reference.frame_id == candidate.frame_id
        and reference.class_name == candidate.class_name
    )


def is_gt_match_candidate(gt: GroundTruthAnnotation, candidate: Detection) -> bool:
    return (
        gt.camera_id == candidate.camera_id
        and gt.frame_id == candidate.frame_id
        and normalize_class_name(gt.class_name) == normalize_class_name(candidate.class_name)
    )
