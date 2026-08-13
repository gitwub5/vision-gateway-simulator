"""ROI budget and fallback decisions."""

from __future__ import annotations

from dataclasses import dataclass

from common import FrameSize, ROI
from roi_generator.config import RoiGeneratorConfig


@dataclass(frozen=True)
class BudgetFallbackDecision:
    should_fallback: bool
    reason: str | None = None


def evaluate_budget_fallback(rois: list[ROI], frame_size: FrameSize, config: RoiGeneratorConfig) -> BudgetFallbackDecision:
    if not rois:
        return BudgetFallbackDecision(False)
    if len(rois) > config.max_roi_per_frame:
        return BudgetFallbackDecision(True, "max_roi_per_frame")

    total_roi_area = sum(roi.area() for roi in rois)
    frame_area = frame_size.area()
    if frame_area <= 0:
        return BudgetFallbackDecision(True, "invalid_frame_area")
    if total_roi_area / frame_area > config.max_total_roi_area_ratio:
        return BudgetFallbackDecision(True, "max_total_roi_area_ratio")
    return BudgetFallbackDecision(False)


def should_fallback_to_full_frame(rois: list[ROI], frame_size: FrameSize, config: RoiGeneratorConfig) -> bool:
    return evaluate_budget_fallback(rois, frame_size, config).should_fallback
