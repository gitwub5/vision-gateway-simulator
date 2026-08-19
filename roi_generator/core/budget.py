"""ROI budget and fallback decisions."""

from __future__ import annotations

from dataclasses import dataclass

from common import FrameSize, ROI
from roi_generator.core.config import RoiGeneratorConfig
from roi_generator.core.decision_reasons import BUDGET_OVERFLOW, INVALID_FRAME_AREA, ROI_AREA_NEAR_FULL_FRAME


@dataclass(frozen=True)
class BudgetFallbackDecision:
    should_fallback: bool
    reason: str | None = None


def evaluate_budget_fallback(rois: list[ROI], frame_size: FrameSize, config: RoiGeneratorConfig) -> BudgetFallbackDecision:
    if not rois:
        return BudgetFallbackDecision(False)
    if len(rois) > config.max_roi_per_frame:
        return BudgetFallbackDecision(True, BUDGET_OVERFLOW)

    total_roi_area = sum(roi.area() for roi in rois)
    frame_area = frame_size.area()
    if frame_area <= 0:
        return BudgetFallbackDecision(True, INVALID_FRAME_AREA)
    if total_roi_area / frame_area > config.max_total_roi_area_ratio:
        return BudgetFallbackDecision(True, ROI_AREA_NEAR_FULL_FRAME)
    return BudgetFallbackDecision(False)


def should_fallback_to_full_frame(rois: list[ROI], frame_size: FrameSize, config: RoiGeneratorConfig) -> bool:
    return evaluate_budget_fallback(rois, frame_size, config).should_fallback
