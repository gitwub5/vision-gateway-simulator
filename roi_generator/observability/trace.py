"""Debug and observability records for ROI generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from common import FramePacket, ROI
from roi_generator.core.budget import BudgetFallbackDecision
from roi_generator.core.config import RoiGeneratorConfig
from roi_generator.core.contract import GateDecision
from roi_generator.signals.event_encoder import EventMaps


@dataclass(frozen=True)
class ComponentTrace:
    component_id: int
    bbox: ROI
    component_area_ratio: float
    bbox_width: int
    bbox_height: int
    bbox_aspect_ratio: float
    fill_density: float
    center_x: float
    center_y: float

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "bbox_xywh": self.bbox.xywh(),
            "component_area_ratio": self.component_area_ratio,
            "bbox_width": self.bbox_width,
            "bbox_height": self.bbox_height,
            "bbox_aspect_ratio": self.bbox_aspect_ratio,
            "fill_density": self.fill_density,
            "center_x": self.center_x,
            "center_y": self.center_y,
        }


@dataclass(frozen=True)
class TileTrace:
    tile_id: int
    row: int
    col: int
    bbox: ROI
    motion_density: float
    selected: bool

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "tile_id": self.tile_id,
            "row": self.row,
            "col": self.col,
            "bbox_xywh": self.bbox.xywh(),
            "motion_density": self.motion_density,
            "selected": self.selected,
        }


@dataclass(frozen=True)
class RoiGenerationTrace:
    filtered_motion_map: Any | None
    candidate_analysis_rois: list[ROI]
    merged_analysis_rois: list[ROI]
    final_rois: list[ROI]
    component_traces: list[ComponentTrace] = field(default_factory=list)
    tile_traces: list[TileTrace] = field(default_factory=list)
    raw_component_count: int = 0
    filtered_component_count: int = 0
    motion_density: float = 0.0


@dataclass(frozen=True)
class ComponentMetadataRecord:
    camera_id: str
    source_id: str
    frame_id: int
    timestamp: float
    policy_label: str
    component: ComponentTrace

    def to_json_dict(self) -> dict[str, Any]:
        data = {
            "camera_id": self.camera_id,
            "source_id": self.source_id,
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "policy_label": self.policy_label,
        }
        data.update(self.component.to_json_dict())
        return data


@dataclass(frozen=True)
class TileMetadataRecord:
    camera_id: str
    source_id: str
    frame_id: int
    timestamp: float
    policy_label: str
    tile: TileTrace

    def to_json_dict(self) -> dict[str, Any]:
        data = {
            "camera_id": self.camera_id,
            "source_id": self.source_id,
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "policy_label": self.policy_label,
        }
        data.update(self.tile.to_json_dict())
        return data


@dataclass(frozen=True)
class PolicyTraceRecord:
    camera_id: str
    source_id: str
    frame_id: int
    timestamp: float
    policy_label: str
    decision_reason: str | None
    trigger_type: str
    roi_count: int
    raw_component_count: int
    filtered_component_count: int
    merged_roi_count: int
    selected_tile_count: int
    tile_group_count: int
    motion_density: float
    final_roi_area_ratio: float
    roi_batch_slots_used: int
    estimated_tensor_pixels: int
    tensor_batch_cost: int
    effective_input_area: int
    feedback_candidate_count: int = 0
    feedback_assisted_roi_count: int = 0
    feedback_active_track_count: int = 0
    feedback_stale_track_count: int = 0

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "source_id": self.source_id,
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "policy_label": self.policy_label,
            "decision_reason": self.decision_reason,
            "trigger_type": self.trigger_type,
            "roi_count": self.roi_count,
            "raw_component_count": self.raw_component_count,
            "filtered_component_count": self.filtered_component_count,
            "merged_roi_count": self.merged_roi_count,
            "selected_tile_count": self.selected_tile_count,
            "tile_group_count": self.tile_group_count,
            "motion_density": self.motion_density,
            "final_roi_area_ratio": self.final_roi_area_ratio,
            "roi_batch_slots_used": self.roi_batch_slots_used,
            "estimated_tensor_pixels": self.estimated_tensor_pixels,
            "tensor_batch_cost": self.tensor_batch_cost,
            "effective_input_area": self.effective_input_area,
            "feedback_candidate_count": self.feedback_candidate_count,
            "feedback_assisted_roi_count": self.feedback_assisted_roi_count,
            "feedback_active_track_count": self.feedback_active_track_count,
            "feedback_stale_track_count": self.feedback_stale_track_count,
        }


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
    feedback_rois: list[ROI] = field(default_factory=list)


class RoiDebugSink(Protocol):
    def write(self, snapshot: RoiDebugSnapshot) -> None:
        raise NotImplementedError
