"""Compressed-domain signal prototype reporting."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common.io import write_json, write_text


@dataclass(frozen=True)
class CompressionFrameRecord:
    frame_index: int
    timestamp: float | None
    pict_type: str
    key_frame: bool
    packet_size: int | None

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CompressionSignalReport:
    dataset_config: str
    experiment_name: str
    dataset_type: str
    input_path: str
    status: str
    reason: str
    frame_count: int = 0
    key_frame_count: int = 0
    average_packet_size: float = 0.0
    max_packet_size: int = 0
    min_packet_size: int = 0
    packet_size_coefficient_of_variation: float = 0.0
    pict_type_counts: dict[str, int] = field(default_factory=dict)

    @property
    def key_frame_rate(self) -> float:
        if self.frame_count == 0:
            return 0.0
        return self.key_frame_count / self.frame_count

    @property
    def metadata_available(self) -> bool:
        return self.status == "available"

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "dataset_config": self.dataset_config,
            "experiment_name": self.experiment_name,
            "dataset_type": self.dataset_type,
            "input_path": self.input_path,
            "status": self.status,
            "reason": self.reason,
            "metadata_available": self.metadata_available,
            "frame_count": self.frame_count,
            "key_frame_count": self.key_frame_count,
            "key_frame_rate": self.key_frame_rate,
            "average_packet_size": self.average_packet_size,
            "max_packet_size": self.max_packet_size,
            "min_packet_size": self.min_packet_size,
            "packet_size_coefficient_of_variation": self.packet_size_coefficient_of_variation,
            "pict_type_counts": self.pict_type_counts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Compression Signal Prototype Report",
            "",
            "## Scope",
            "",
            f"- Experiment: `{self.experiment_name}`",
            f"- Dataset config: `{self.dataset_config}`",
            f"- Dataset type: `{self.dataset_type}`",
            f"- Input path: `{self.input_path}`",
            f"- Status: `{self.status}`",
            f"- Reason: {self.reason}",
            "",
            "## Metadata Summary",
            "",
            f"- Frames inspected: {self.frame_count}",
            f"- Key frames: {self.key_frame_count}",
            f"- Key-frame rate: {self.key_frame_rate:.3f}",
            f"- Average packet size: {self.average_packet_size:.3f}",
            f"- Packet size coefficient of variation: {self.packet_size_coefficient_of_variation:.3f}",
            f"- Min packet size: {self.min_packet_size}",
            f"- Max packet size: {self.max_packet_size}",
            "",
            "## Picture Types",
            "",
        ]
        if self.pict_type_counts:
            for pict_type, count in sorted(self.pict_type_counts.items()):
                lines.append(f"- `{pict_type}`: {count}")
        else:
            lines.append("- unavailable")
        lines.append("")
        return "\n".join(lines)


def build_compression_signal_report(
    records: Iterable[CompressionFrameRecord],
    dataset_config: str,
    experiment_name: str,
    dataset_type: str,
    input_path: str,
    status: str = "available",
    reason: str = "encoded metadata extracted",
) -> CompressionSignalReport:
    frame_records = list(records)
    packet_sizes = [record.packet_size for record in frame_records if record.packet_size is not None]
    average_packet_size = _average(packet_sizes)
    return CompressionSignalReport(
        dataset_config=dataset_config,
        experiment_name=experiment_name,
        dataset_type=dataset_type,
        input_path=input_path,
        status=status,
        reason=reason,
        frame_count=len(frame_records),
        key_frame_count=sum(1 for record in frame_records if record.key_frame),
        average_packet_size=average_packet_size,
        max_packet_size=max(packet_sizes, default=0),
        min_packet_size=min(packet_sizes, default=0),
        packet_size_coefficient_of_variation=_coefficient_of_variation(packet_sizes),
        pict_type_counts=dict(Counter(record.pict_type or "unknown" for record in frame_records)),
    )


def unavailable_compression_signal_report(
    dataset_config: str,
    experiment_name: str,
    dataset_type: str,
    input_path: str,
    reason: str,
) -> CompressionSignalReport:
    return CompressionSignalReport(
        dataset_config=dataset_config,
        experiment_name=experiment_name,
        dataset_type=dataset_type,
        input_path=input_path,
        status="unavailable",
        reason=reason,
    )


def write_compression_signal_report_json(report: CompressionSignalReport, output_path: str | Path) -> None:
    write_json(report.to_json_dict(), output_path)


def write_compression_signal_report_markdown(report: CompressionSignalReport, output_path: str | Path) -> None:
    write_text(report.to_markdown(), output_path)


def _average(values: Iterable[int]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)


def _coefficient_of_variation(values: Iterable[int]) -> float:
    items = list(values)
    if not items:
        return 0.0
    mean = sum(items) / len(items)
    if mean == 0:
        return 0.0
    variance = sum((item - mean) ** 2 for item in items) / len(items)
    return (variance**0.5) / mean
