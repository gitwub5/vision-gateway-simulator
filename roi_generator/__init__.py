"""Rule-based ROI generator emulator."""

from roi_generator.gate import (
    BudgetFallbackDecision,
    GateDecision,
    RoiDebugSnapshot,
    RoiGenerationTrace,
    RoiGeneratorConfig,
    RuleBasedRoiGenerator,
    evaluate_budget_fallback,
    is_periodic_full_frame,
    load_roi_generator_config,
    should_fallback_to_full_frame,
)
from roi_generator.metadata import (
    GateFrameMetadataWriter,
    ROIMetadataWriter,
    build_roi_id,
    frame_metadata_from_gate_decision,
    roi_metadata_from_gate_decision,
)

__all__ = [
    "GateDecision",
    "BudgetFallbackDecision",
    "RoiDebugSnapshot",
    "RoiGenerationTrace",
    "RoiGeneratorConfig",
    "RuleBasedRoiGenerator",
    "evaluate_budget_fallback",
    "is_periodic_full_frame",
    "load_roi_generator_config",
    "should_fallback_to_full_frame",
    "GateFrameMetadataWriter",
    "ROIMetadataWriter",
    "build_roi_id",
    "frame_metadata_from_gate_decision",
    "roi_metadata_from_gate_decision",
]
