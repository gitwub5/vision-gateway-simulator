"""Shared target-class normalization and filtering helpers."""

from __future__ import annotations

from collections.abc import Iterable

from common import Detection, GroundTruthAnnotation


CLASS_ALIASES = {
    "bike/bicycle": "bicycle",
    "bike": "bicycle",
    "person": "person",
    "car": "car",
    "truck": "vehicle",
    "bus": "vehicle",
    "vehicle": "vehicle",
    "carrying_object": "carrying_object",
}


def normalize_class_name(class_name: str) -> str:
    normalized = class_name.strip().lower()
    return CLASS_ALIASES.get(normalized, normalized)


def normalize_target_classes(target_classes: Iterable[str] | None) -> set[str]:
    return {
        normalize_class_name(str(class_name))
        for class_name in target_classes or []
        if str(class_name).strip()
    }


def filter_gt_by_target_classes(
    records: Iterable[GroundTruthAnnotation],
    target_classes: Iterable[str] | set[str] | None,
) -> list[GroundTruthAnnotation]:
    normalized_targets = _as_normalized_target_set(target_classes)
    if not normalized_targets:
        return list(records)
    return [
        record
        for record in records
        if normalize_class_name(record.class_name) in normalized_targets
    ]


def filter_detections_by_target_classes(
    records: Iterable[Detection],
    target_classes: Iterable[str] | set[str] | None,
) -> list[Detection]:
    normalized_targets = _as_normalized_target_set(target_classes)
    if not normalized_targets:
        return list(records)
    return [
        record
        for record in records
        if normalize_class_name(record.class_name) in normalized_targets
    ]


def _as_normalized_target_set(target_classes: Iterable[str] | set[str] | None) -> set[str]:
    if not target_classes:
        return set()
    return normalize_target_classes(target_classes)
