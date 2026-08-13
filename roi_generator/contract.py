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
    event_maps: EventMaps | None = field(default=None, repr=False, compare=False)
