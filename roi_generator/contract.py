"""Gate decision contract shared by ROI generation and downstream stages."""

from __future__ import annotations

from dataclasses import dataclass, field

from common import FrameSize, ROI, TriggerType
from roi_generator.signals.event_encoder import EventMaps


@dataclass(frozen=True)
class GateDecision:
    camera_id: str
    frame_id: int
    timestamp: float
    trigger_type: TriggerType
    rois: list[ROI]
    original_frame_size: FrameSize
    analysis_frame_size: FrameSize
    gate_latency_ms: float
    should_run_full_frame: bool = False
    policy_label: str = "component_bbox"
    decision_reason: str | None = None
    roi_batch_slots_used: int = 0
    tile_group_count: int = 0
    selected_tile_count: int = 0
    estimated_tensor_pixels: int = 0
    tensor_batch_cost: int = 0
    effective_input_area: int = 0
    raw_component_count: int = 0
    filtered_component_count: int = 0
    merged_roi_count: int = 0
    motion_density: float = 0.0
    final_roi_area_ratio: float = 0.0
    event_maps: EventMaps | None = field(default=None, repr=False, compare=False)
