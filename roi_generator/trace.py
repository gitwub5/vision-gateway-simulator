"""Debug and observability records for ROI generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from common import FramePacket, ROI
from roi_generator.budget import BudgetFallbackDecision
from roi_generator.config import RoiGeneratorConfig
from roi_generator.contract import GateDecision
from roi_generator.signals.event_encoder import EventMaps


@dataclass(frozen=True)
class RoiGenerationTrace:
    filtered_motion_map: Any | None
    candidate_analysis_rois: list[ROI]
    merged_analysis_rois: list[ROI]
    final_rois: list[ROI]


@dataclass(frozen=True)
class RoiDebugSnapshot:
    packet: FramePacket
    config: RoiGeneratorConfig
    analysis_gray: Any
    previous_analysis_gray: Any | None
    event_maps: EventMaps | None
    generation_trace: RoiGenerationTrace
    decision: GateDecision
    budget_fallback: BudgetFallbackDecision


class RoiDebugSink(Protocol):
    def write(self, snapshot: RoiDebugSnapshot) -> None:
        raise NotImplementedError
