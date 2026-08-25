"""ROI gate trace and metadata helpers."""

from roi_generator.observability.metadata import (
    ComponentMetadataWriter,
    GateFrameMetadataWriter,
    PolicyTraceWriter,
    ROIMetadataWriter,
    TileMetadataWriter,
    build_roi_id,
    component_metadata_from_trace,
    frame_metadata_from_gate_decision,
    policy_trace_from_gate_decision,
    read_tile_metadata_jsonl,
    roi_metadata_from_gate_decision,
    tile_metadata_from_trace,
)
from roi_generator.observability.trace import (
    ComponentMetadataRecord,
    ComponentTrace,
    PolicyTraceRecord,
    RoiDebugSink,
    RoiDebugSnapshot,
    RoiGenerationTrace,
    TileMetadataRecord,
    TileTrace,
)

__all__ = [
    "ComponentMetadataRecord",
    "ComponentMetadataWriter",
    "ComponentTrace",
    "GateFrameMetadataWriter",
    "PolicyTraceRecord",
    "PolicyTraceWriter",
    "ROIMetadataWriter",
    "RoiDebugSink",
    "RoiDebugSnapshot",
    "RoiGenerationTrace",
    "TileMetadataRecord",
    "TileMetadataWriter",
    "TileTrace",
    "build_roi_id",
    "component_metadata_from_trace",
    "frame_metadata_from_gate_decision",
    "policy_trace_from_gate_decision",
    "read_tile_metadata_jsonl",
    "roi_metadata_from_gate_decision",
    "tile_metadata_from_trace",
]
