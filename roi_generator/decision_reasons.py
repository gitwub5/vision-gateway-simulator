"""Canonical gate decision reasons used in metadata and reports."""

from __future__ import annotations

from common import TriggerType

INITIAL_FRAME = "initial_frame"
ANALYSIS_SIZE_CHANGED = "analysis_size_changed"
PERIODIC_FULL_FRAME = "periodic_full_frame"
ROI_SELECTED = "roi_selected"
TEMPORAL_HOLD = "temporal_hold"
NO_ROI = "no_roi"
BUDGET_OVERFLOW = "budget_overflow"
ROI_AREA_NEAR_FULL_FRAME = "roi_area_near_full_frame"
INVALID_FRAME_AREA = "invalid_frame_area"


def reason_for_trigger(trigger_type: TriggerType) -> str:
    if trigger_type == TriggerType.ROI:
        return ROI_SELECTED
    if trigger_type == TriggerType.HOLD:
        return TEMPORAL_HOLD
    if trigger_type == TriggerType.NONE:
        return NO_ROI
    return trigger_type.value
