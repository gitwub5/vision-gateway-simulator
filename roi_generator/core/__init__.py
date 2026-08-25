"""Runtime ROI gate core.

This package contains the code path used to turn frames into gate decisions.
Evaluation records and debug serialization live in `roi_generator.observability`.
"""

from roi_generator.core.budget import BudgetFallbackDecision, evaluate_budget_fallback, should_fallback_to_full_frame
from roi_generator.core.config import RoiGeneratorConfig, load_roi_generator_config
from roi_generator.core.contract import GateDecision
from roi_generator.core.gate import (
    RuleBasedRoiGenerator,
    final_roi_area_ratio,
    is_periodic_full_frame,
    selected_tile_count,
    sort_rois_by_area,
)

__all__ = [
    "BudgetFallbackDecision",
    "GateDecision",
    "RoiGeneratorConfig",
    "RuleBasedRoiGenerator",
    "evaluate_budget_fallback",
    "final_roi_area_ratio",
    "is_periodic_full_frame",
    "load_roi_generator_config",
    "selected_tile_count",
    "should_fallback_to_full_frame",
    "sort_rois_by_area",
]
