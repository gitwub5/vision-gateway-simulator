"""ROI metadata serialization helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from common import GateFrameMetadata, ROIMetadata
from common.io import write_jsonl
from roi_generator.gate import GateDecision


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
    )


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
