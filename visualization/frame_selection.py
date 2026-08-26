"""Frame selection policies shared by ROI review and comparison renderers."""

from __future__ import annotations

from typing import Iterable

from evaluation.metrics.roi_containment import contains_bbox
from visualization.artifacts import FrameKey, RoiRunArtifacts


VALID_PRESETS = ("disagreement", "missed", "cost", "explicit")


class SimpleRoi:
    def __init__(self, record: dict) -> None:
        x, y, w, h = record["roi_xywh"]
        self.x = int(x)
        self.y = int(y)
        self.w = int(w)
        self.h = int(h)


def select_frame_keys(
    runs: list[RoiRunArtifacts],
    preset: str,
    max_frames: int,
    explicit: Iterable[FrameKey] = (),
) -> list[FrameKey]:
    if preset not in VALID_PRESETS:
        raise ValueError(f"Unsupported frame selection preset: {preset}")
    if preset == "explicit":
        return sorted(set(explicit))[:max_frames]
    if not runs:
        return []

    gt_by_frame = runs[0].ground_truth_by_frame
    scored: list[tuple[float, FrameKey]] = []
    for key, gt_records in gt_by_frame.items():
        contained_counts = [
            count_contained_gt(run.rois_by_frame.get(key, []), gt_records)
            for run in runs
        ]
        if preset == "disagreement":
            score = float(max(contained_counts) - min(contained_counts))
        elif preset == "missed":
            score = float(max(len(gt_records) - count for count in contained_counts))
        else:
            roi_costs = [
                sum(roi_area(record) for record in run.rois_by_frame.get(key, []))
                + (1_000_000 if run.frames_by_frame.get(key, {}).get("should_run_full_frame") else 0)
                for run in runs
            ]
            score = float(max(roi_costs) - min(roi_costs))
        if score > 0:
            scored.append((score, key))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = sorted(key for _, key in scored[:max_frames])
    if selected:
        return selected
    return sorted(gt_by_frame)[:max_frames]


def select_review_frame_keys(
    run: RoiRunArtifacts,
    preset: str,
    max_frames: int,
    explicit: Iterable[FrameKey] = (),
) -> list[FrameKey]:
    if preset == "explicit":
        return sorted(set(explicit))[:max_frames]
    if preset not in {"missed", "cost"}:
        raise ValueError(f"Unsupported review frame selection preset: {preset}")

    keys = set(run.frames_by_frame) | set(run.ground_truth_by_frame) | set(run.rois_by_frame)
    scored: list[tuple[float, FrameKey]] = []
    for key in keys:
        rois = run.rois_by_frame.get(key, [])
        gt_records = run.ground_truth_by_frame.get(key, [])
        frame_record = run.frames_by_frame.get(key, {})
        area = sum(roi_area(record) for record in rois)
        if preset == "cost":
            score = float(area)
            if frame_record.get("should_run_full_frame"):
                score += 1_000_000_000
        else:
            missed = len(gt_records) - count_contained_gt(rois, gt_records)
            score = float(missed * 100)
            if gt_records and not rois:
                score += 50
            if frame_record.get("should_run_full_frame"):
                score += 25
            if float(frame_record.get("final_roi_area_ratio", 0.0)) >= 0.5:
                score += 10
        if score > 0:
            scored.append((score, key))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [key for _, key in scored[:max_frames]]


def review_failure_reasons(run: RoiRunArtifacts, key: FrameKey) -> list[str]:
    rois = run.rois_by_frame.get(key, [])
    gt_records = run.ground_truth_by_frame.get(key, [])
    frame_record = run.frames_by_frame.get(key, {})
    reasons: list[str] = []
    missed = len(gt_records) - count_contained_gt(rois, gt_records)
    if gt_records and not rois:
        reasons.append("no_roi")
    if missed:
        reasons.append("boundary_or_signal_miss")
    if frame_record.get("should_run_full_frame"):
        reasons.append("fallback")
    if float(frame_record.get("final_roi_area_ratio", 0.0)) >= 0.5:
        reasons.append("oversized_roi")
    return reasons


def count_contained_gt(
    roi_records: list[dict],
    gt_records: list[dict],
) -> int:
    return sum(
        1
        for gt in gt_records
        if any(contains_bbox(SimpleRoi(roi), gt["bbox_xyxy"]) for roi in roi_records)
    )


def roi_area(record: dict) -> int:
    _, _, width, height = record["roi_xywh"]
    return max(0, int(width)) * max(0, int(height))
