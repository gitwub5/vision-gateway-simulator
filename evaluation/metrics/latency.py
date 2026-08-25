"""Latency metric helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from common import GateFrameMetadata


def average_ms(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


@dataclass(frozen=True)
class LatencySummary:
    full_frame_average_latency_ms: float
    roi_average_latency_ms: float
    gate_average_latency_ms: float
    gate_max_latency_ms: float

    def to_json_dict(self) -> dict:
        return {
            "full_frame_average_latency_ms": self.full_frame_average_latency_ms,
            "roi_average_latency_ms": self.roi_average_latency_ms,
            "gate_average_latency_ms": self.gate_average_latency_ms,
            "gate_max_latency_ms": self.gate_max_latency_ms,
        }


def summarize_latency(
    full_frame_metrics: dict,
    roi_metrics: dict,
    frame_records: Iterable[GateFrameMetadata],
) -> LatencySummary:
    gate_values = [record.gate_latency_ms for record in frame_records]
    return LatencySummary(
        full_frame_average_latency_ms=float(full_frame_metrics.get("average_latency_ms", 0.0)),
        roi_average_latency_ms=float(roi_metrics.get("average_latency_ms", 0.0)),
        gate_average_latency_ms=average_ms(gate_values),
        gate_max_latency_ms=max(gate_values) if gate_values else 0.0,
    )
