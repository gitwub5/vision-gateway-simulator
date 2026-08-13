"""Shared helpers for validation experiment scripts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common.io import load_yaml_config, write_json
from data_loader import create_dataset_stream
from roi_generator import (
    ComponentMetadataWriter,
    GateFrameMetadataWriter,
    PolicyTraceWriter,
    ROIMetadataWriter,
    RuleBasedRoiGenerator,
    TileMetadataWriter,
    component_metadata_from_trace,
    frame_metadata_from_gate_decision,
    policy_trace_from_gate_decision,
    roi_metadata_from_gate_decision,
    tile_metadata_from_trace,
)


def load_validation_config(config_path: str | Path) -> dict[str, Any]:
    config = load_yaml_config(config_path)
    validation = config.get("validation")
    return dict(validation) if validation else {}


def run_roi_generator_metadata(
    dataset_config,
    roi_generator_config,
    roi_output: Path,
    frame_output: Path,
    component_output: Path | None = None,
    tile_output: Path | None = None,
    policy_trace_output: Path | None = None,
    debug_sink=None,
) -> dict[str, Any]:
    stream = create_dataset_stream(dataset_config)
    generator = RuleBasedRoiGenerator(roi_generator_config, debug_sink=debug_sink)
    roi_writer = ROIMetadataWriter(roi_output)
    frame_writer = GateFrameMetadataWriter(frame_output)
    component_writer = ComponentMetadataWriter(component_output) if component_output is not None else None
    tile_writer = TileMetadataWriter(tile_output) if tile_output is not None else None
    policy_trace_writer = PolicyTraceWriter(policy_trace_output) if policy_trace_output is not None else None
    processed_frames = 0
    roi_records_count = 0
    component_records_count = 0
    tile_records_count = 0

    for packet in stream:
        decision = generator.process(packet)
        roi_records = roi_metadata_from_gate_decision(decision)
        frame_record = frame_metadata_from_gate_decision(decision)
        component_records = component_metadata_from_trace(decision, generator.last_generation_trace)
        tile_records = tile_metadata_from_trace(decision, generator.last_generation_trace)
        roi_writer.write_many(roi_records)
        frame_writer.write(frame_record)
        if component_writer is not None:
            component_writer.write_many(component_records)
        if tile_writer is not None:
            tile_writer.write_many(tile_records)
        if policy_trace_writer is not None:
            policy_trace_writer.write(policy_trace_from_gate_decision(decision))
        processed_frames += 1
        roi_records_count += len(roi_records)
        component_records_count += len(component_records)
        tile_records_count += len(tile_records)

    return {
        "processed_frames": processed_frames,
        "roi_records": roi_records_count,
        "component_records": component_records_count,
        "tile_records": tile_records_count,
        "debug": debug_sink.summary() if debug_sink and hasattr(debug_sink, "summary") else None,
    }


def run_gate_metadata(dataset_config, gate_config, roi_output: Path, frame_output: Path) -> dict[str, Any]:
    return run_roi_generator_metadata(dataset_config, gate_config, roi_output, frame_output)
