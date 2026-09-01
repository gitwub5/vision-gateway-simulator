"""ROI metadata serialization helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from common import GateFrameMetadata, ROI, ROIMetadata
from common.io import read_jsonl, write_jsonl
from roi_generator.core.gate import GateDecision
from roi_generator.observability.trace import (
    ComponentMetadataRecord,
    PolicyTraceRecord,
    RoiGenerationTrace,
    TileMetadataRecord,
    TileTrace,
)


class JsonSerializable(Protocol):
    def to_json_dict(self) -> dict[str, Any]:
        raise NotImplementedError


def build_roi_id(camera_id: str, frame_id: int, roi_index: int) -> str:
    safe_camera_id = camera_id.replace("/", "_").replace(" ", "_")
    return f"{safe_camera_id}_f{frame_id:06d}_roi_{roi_index:03d}"


def roi_metadata_from_gate_decision(decision: GateDecision) -> list[ROIMetadata]:
    records: list[ROIMetadata] = []
    for index, roi in enumerate(decision.rois, start=1):
        records.append(
            ROIMetadata(
                camera_id=decision.camera_id,
                frame_id=decision.frame_id,
                timestamp=decision.timestamp,
                roi_id=build_roi_id(decision.camera_id, decision.frame_id, index),
                original_frame_size=decision.original_frame_size,
                analysis_frame_size=decision.analysis_frame_size,
                roi=roi,
                trigger_type=decision.trigger_type,
                policy_label=decision.policy_label,
                decision_reason=decision.decision_reason,
                batch_slot=index - 1,
                processing_width=decision.analysis_frame_size.width,
                processing_height=decision.analysis_frame_size.height,
            )
        )
    return records


def frame_metadata_from_gate_decision(decision: GateDecision) -> GateFrameMetadata:
    return GateFrameMetadata(
        camera_id=decision.camera_id,
        frame_id=decision.frame_id,
        timestamp=decision.timestamp,
        trigger_type=decision.trigger_type,
        roi_count=len(decision.rois),
        should_run_full_frame=decision.should_run_full_frame,
        gate_latency_ms=decision.gate_latency_ms,
        original_frame_size=decision.original_frame_size,
        analysis_frame_size=decision.analysis_frame_size,
        policy_label=decision.policy_label,
        decision_reason=decision.decision_reason,
        roi_batch_slots_used=decision.roi_batch_slots_used,
        tile_group_count=decision.tile_group_count,
        selected_tile_count=decision.selected_tile_count,
        estimated_tensor_pixels=decision.estimated_tensor_pixels,
        tensor_batch_cost=decision.tensor_batch_cost,
        effective_input_area=decision.effective_input_area,
        raw_component_count=decision.raw_component_count,
        filtered_component_count=decision.filtered_component_count,
        merged_roi_count=decision.merged_roi_count,
        motion_density=decision.motion_density,
        final_roi_area_ratio=decision.final_roi_area_ratio,
        feedback_candidate_count=decision.feedback_candidate_count,
        feedback_assisted_roi_count=decision.feedback_assisted_roi_count,
        feedback_active_track_count=decision.feedback_active_track_count,
        feedback_stale_track_count=decision.feedback_stale_track_count,
    )


def policy_trace_from_gate_decision(decision: GateDecision) -> PolicyTraceRecord:
    return PolicyTraceRecord(
        camera_id=decision.camera_id,
        source_id=decision.camera_id,
        frame_id=decision.frame_id,
        timestamp=decision.timestamp,
        policy_label=decision.policy_label,
        decision_reason=decision.decision_reason,
        trigger_type=decision.trigger_type.value,
        roi_count=len(decision.rois),
        raw_component_count=decision.raw_component_count,
        filtered_component_count=decision.filtered_component_count,
        merged_roi_count=decision.merged_roi_count,
        selected_tile_count=decision.selected_tile_count,
        tile_group_count=decision.tile_group_count,
        motion_density=decision.motion_density,
        final_roi_area_ratio=decision.final_roi_area_ratio,
        roi_batch_slots_used=decision.roi_batch_slots_used,
        estimated_tensor_pixels=decision.estimated_tensor_pixels,
        tensor_batch_cost=decision.tensor_batch_cost,
        effective_input_area=decision.effective_input_area,
        feedback_candidate_count=decision.feedback_candidate_count,
        feedback_assisted_roi_count=decision.feedback_assisted_roi_count,
        feedback_active_track_count=decision.feedback_active_track_count,
        feedback_stale_track_count=decision.feedback_stale_track_count,
    )


def component_metadata_from_trace(
    decision: GateDecision,
    trace: RoiGenerationTrace | None,
) -> list[ComponentMetadataRecord]:
    if trace is None:
        return []
    return [
        ComponentMetadataRecord(
            camera_id=decision.camera_id,
            source_id=decision.camera_id,
            frame_id=decision.frame_id,
            timestamp=decision.timestamp,
            policy_label=decision.policy_label,
            component=component_trace,
        )
        for component_trace in trace.component_traces
    ]


def tile_metadata_from_trace(
    decision: GateDecision,
    trace: RoiGenerationTrace | None,
) -> list[TileMetadataRecord]:
    if trace is None:
        return []
    return [
        TileMetadataRecord(
            camera_id=decision.camera_id,
            source_id=decision.camera_id,
            frame_id=decision.frame_id,
            timestamp=decision.timestamp,
            policy_label=decision.policy_label,
            tile=tile_trace,
        )
        for tile_trace in trace.tile_traces
    ]


def read_tile_metadata_jsonl(input_path: str | Path) -> list[TileMetadataRecord]:
    records: list[TileMetadataRecord] = []
    for data in read_jsonl(input_path):
        x, y, w, h = data["bbox_xywh"]
        records.append(
            TileMetadataRecord(
                camera_id=str(data["camera_id"]),
                source_id=str(data.get("source_id", data["camera_id"])),
                frame_id=int(data["frame_id"]),
                timestamp=float(data["timestamp"]),
                policy_label=str(data.get("policy_label", "component_bbox")),
                tile=TileTrace(
                    tile_id=int(data["tile_id"]),
                    row=int(data["row"]),
                    col=int(data["col"]),
                    bbox=ROI(
                        x=int(x),
                        y=int(y),
                        w=int(w),
                        h=int(h),
                        score=float(data.get("motion_density", 0.0)),
                        coord_system="analysis_frame",
                    ),
                    motion_density=float(data.get("motion_density", 0.0)),
                    selected=bool(data.get("selected", False)),
                    motion_threshold=float(data.get("motion_threshold", 0.0)),
                    selection_reason=str(data.get("selection_reason", "motion_threshold")),
                ),
            )
        )
    return records


class JsonlWriter:
    def __init__(self, output_path: str | Path, append: bool = False) -> None:
        self.output_path = Path(output_path)
        self.append = append
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: JsonSerializable) -> None:
        self.write_many([record])

    def write_many(self, records: list[JsonSerializable]) -> None:
        write_jsonl(records, self.output_path, append=self.append)
        self.append = True


class ROIMetadataWriter:
    def __init__(self, output_path: str | Path, append: bool = False) -> None:
        self._writer = JsonlWriter(output_path, append=append)

    def write(self, record: ROIMetadata) -> None:
        self._writer.write(record)

    def write_many(self, records: list[ROIMetadata]) -> None:
        self._writer.write_many(records)

    def write_all(self, records: list[ROIMetadata]) -> None:
        self._writer.append = False
        self._writer.write_many(records)


class GateFrameMetadataWriter:
    def __init__(self, output_path: str | Path, append: bool = False) -> None:
        self._writer = JsonlWriter(output_path, append=append)

    def write(self, record: GateFrameMetadata) -> None:
        self._writer.write(record)

    def write_many(self, records: list[GateFrameMetadata]) -> None:
        self._writer.write_many(records)


class ComponentMetadataWriter:
    def __init__(self, output_path: str | Path, append: bool = False) -> None:
        self._writer = JsonlWriter(output_path, append=append)

    def write_many(self, records: list[ComponentMetadataRecord]) -> None:
        self._writer.write_many(records)


class TileMetadataWriter:
    def __init__(self, output_path: str | Path, append: bool = False) -> None:
        self._writer = JsonlWriter(output_path, append=append)

    def write_many(self, records: list[TileMetadataRecord]) -> None:
        self._writer.write_many(records)


class PolicyTraceWriter:
    def __init__(self, output_path: str | Path, append: bool = False) -> None:
        self._writer = JsonlWriter(output_path, append=append)

    def write(self, record: PolicyTraceRecord) -> None:
        self._writer.write(record)
