"""ROI budget and fallback decisions."""

from __future__ import annotations

from dataclasses import dataclass

from common import FrameSize, ROI
from roi_generator.core.config import RoiGeneratorConfig
from roi_generator.core.decision_reasons import (
    BATCH_SLOT_OVERFLOW,
    INVALID_FRAME_AREA,
    ROI_AREA_NEAR_FULL_FRAME,
    TENSOR_BUDGET_OVERFLOW,
    TILE_COUNT_OVERHEAD_EXCEEDS_GAIN,
)


@dataclass(frozen=True)
class BudgetFallbackDecision:
    should_fallback: bool
    reason: str | None = None


@dataclass(frozen=True)
class BudgetCost:
    roi_batch_slots_used: int
    selected_tile_count: int
    tile_group_count: int
    estimated_tensor_pixels: int
    tensor_batch_cost: int
    effective_input_area: int


def estimate_budget_cost(
    rois: list[ROI],
    frame_size: FrameSize,
    selected_tile_count: int = 0,
    tile_group_count: int = 0,
    should_run_full_frame: bool = False,
) -> BudgetCost:
    estimated_tensor_pixels = sum(roi.area() for roi in rois)
    effective_input_area = estimated_tensor_pixels
    if should_run_full_frame:
        effective_input_area += frame_size.area()
    return BudgetCost(
        roi_batch_slots_used=len(rois),
        selected_tile_count=selected_tile_count,
        tile_group_count=tile_group_count,
        estimated_tensor_pixels=estimated_tensor_pixels,
        tensor_batch_cost=estimated_tensor_pixels,
        effective_input_area=effective_input_area,
    )


def evaluate_budget_fallback(
    rois: list[ROI],
    frame_size: FrameSize,
    config: RoiGeneratorConfig,
    selected_tile_count: int = 0,
    tile_group_count: int = 0,
    tile_budget_applies: bool = False,
) -> BudgetFallbackDecision:
    if not config.budget_enabled:
        return BudgetFallbackDecision(False)
    if not rois:
        return BudgetFallbackDecision(False)
    if len(rois) > config.max_roi_per_frame:
        return BudgetFallbackDecision(True, BATCH_SLOT_OVERFLOW)

    total_roi_area = sum(roi.area() for roi in rois)
    frame_area = frame_size.area()
    if frame_area <= 0:
        return BudgetFallbackDecision(True, INVALID_FRAME_AREA)
    if total_roi_area / frame_area > config.max_total_roi_area_ratio:
        return BudgetFallbackDecision(True, ROI_AREA_NEAR_FULL_FRAME)
    if (
        tile_budget_applies
        and config.max_selected_tile_count is not None
        and selected_tile_count > config.max_selected_tile_count
    ):
        return BudgetFallbackDecision(True, TILE_COUNT_OVERHEAD_EXCEEDS_GAIN)
    tensor_batch_cost = estimate_budget_cost(
        rois=rois,
        frame_size=frame_size,
        selected_tile_count=selected_tile_count,
        tile_group_count=tile_group_count,
    ).tensor_batch_cost
    if config.max_tensor_batch_cost is not None and tensor_batch_cost > config.max_tensor_batch_cost:
        return BudgetFallbackDecision(True, TENSOR_BUDGET_OVERFLOW)
    return BudgetFallbackDecision(False)


def should_fallback_to_full_frame(rois: list[ROI], frame_size: FrameSize, config: RoiGeneratorConfig) -> bool:
    return evaluate_budget_fallback(rois, frame_size, config).should_fallback
