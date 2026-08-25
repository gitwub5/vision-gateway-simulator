"""Dataclasses shared across loader, gate, inference, and evaluation code."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class TriggerType(StrEnum):
    ROI = "roi"
    HOLD = "temporal_hold"
    FULL_FRAME = "full_frame"
    FALLBACK_FULL_FRAME = "fallback_full_frame"
    NONE = "none"


@dataclass(frozen=True)
class FrameSize:
    width: int
    height: int

    def area(self) -> int:
        return self.width * self.height

    def as_list(self) -> list[int]:
        return [self.width, self.height]


@dataclass(frozen=True)
class FramePacket:
    camera_id: str
    frame_id: int
    timestamp: float
    frame: Any
    original_size: FrameSize


@dataclass(frozen=True)
class ROI:
    x: int
    y: int
    w: int
    h: int
    score: float = 1.0
    coord_system: str = "original_frame"

    def area(self) -> int:
        return max(self.w, 0) * max(self.h, 0)

    def xywh(self) -> list[int]:
        return [self.x, self.y, self.w, self.h]


@dataclass(frozen=True)
class ROIMetadata:
    camera_id: str
    frame_id: int
    timestamp: float
    roi_id: str
    original_frame_size: FrameSize
    analysis_frame_size: FrameSize
    roi: ROI
    source: str = "rule_based_roi_generator"
    trigger_type: TriggerType = TriggerType.ROI
    policy_label: str = "component_bbox"
    decision_reason: str | None = None
    batch_slot: int | None = None
    processing_width: int | None = None
    processing_height: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        data = {
            "camera_id": self.camera_id,
            "source_id": self.camera_id,
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "roi_id": self.roi_id,
            "original_frame_size": self.original_frame_size.as_list(),
            "analysis_frame_size": self.analysis_frame_size.as_list(),
            "roi_xywh": self.roi.xywh(),
            "score": self.roi.score,
            "source": self.source,
            "trigger_type": self.trigger_type.value,
            "policy_label": self.policy_label,
        }
        if self.decision_reason is not None:
            data["decision_reason"] = self.decision_reason
        if self.batch_slot is not None:
            data["batch_slot"] = self.batch_slot
        if self.processing_width is not None:
            data["processing_width"] = self.processing_width
        if self.processing_height is not None:
            data["processing_height"] = self.processing_height
        return data


@dataclass(frozen=True)
class GateFrameMetadata:
    camera_id: str
    frame_id: int
    timestamp: float
    trigger_type: TriggerType
    roi_count: int
    should_run_full_frame: bool
    gate_latency_ms: float
    original_frame_size: FrameSize
    analysis_frame_size: FrameSize
    source: str = "rule_based_roi_generator"
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
    feedback_candidate_count: int = 0
    feedback_assisted_roi_count: int = 0
    feedback_active_track_count: int = 0
    feedback_stale_track_count: int = 0

    def to_json_dict(self) -> dict[str, Any]:
        data = {
            "camera_id": self.camera_id,
            "source_id": self.camera_id,
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "trigger_type": self.trigger_type.value,
            "roi_count": self.roi_count,
            "should_run_full_frame": self.should_run_full_frame,
            "gate_latency_ms": self.gate_latency_ms,
            "original_frame_size": self.original_frame_size.as_list(),
            "analysis_frame_size": self.analysis_frame_size.as_list(),
            "source": self.source,
            "policy_label": self.policy_label,
            "roi_batch_slots_used": self.roi_batch_slots_used,
            "tile_group_count": self.tile_group_count,
            "selected_tile_count": self.selected_tile_count,
            "estimated_tensor_pixels": self.estimated_tensor_pixels,
            "tensor_batch_cost": self.tensor_batch_cost,
            "effective_input_area": self.effective_input_area,
            "raw_component_count": self.raw_component_count,
            "filtered_component_count": self.filtered_component_count,
            "merged_roi_count": self.merged_roi_count,
            "motion_density": self.motion_density,
            "final_roi_area_ratio": self.final_roi_area_ratio,
            "feedback_candidate_count": self.feedback_candidate_count,
            "feedback_assisted_roi_count": self.feedback_assisted_roi_count,
            "feedback_active_track_count": self.feedback_active_track_count,
            "feedback_stale_track_count": self.feedback_stale_track_count,
        }
        if self.decision_reason is not None:
            data["decision_reason"] = self.decision_reason
        return data


@dataclass(frozen=True)
class Detection:
    camera_id: str
    frame_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: list[float]
    source: str
    roi_id: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GroundTruthAnnotation:
    camera_id: str
    frame_id: int
    class_id: int
    class_name: str
    bbox_xyxy: list[float]
    annotation_id: int | str
    image_id: int | str
    file_name: str
    source: str = "ground_truth"
    iscrowd: int = 0

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentMetrics:
    frame_count: int = 0
    yolo_call_count: int = 0
    yolo_input_pixel_area: int = 0
    average_roi_count: float = 0.0
    average_roi_area_ratio: float = 0.0
    gate_latency_ms: list[float] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)
