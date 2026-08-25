"""GPU workload reduction metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def reduction_ratio(baseline: float, candidate: float) -> float:
    if baseline <= 0:
        return 0.0
    return (baseline - candidate) / baseline


@dataclass(frozen=True)
class WorkloadSummary:
    full_frame_yolo_call_count: int
    roi_yolo_call_count: int
    full_frame_input_pixel_area: int
    roi_input_pixel_area: int

    @property
    def yolo_call_reduction(self) -> float:
        return reduction_ratio(self.full_frame_yolo_call_count, self.roi_yolo_call_count)

    @property
    def input_pixel_area_reduction(self) -> float:
        return reduction_ratio(self.full_frame_input_pixel_area, self.roi_input_pixel_area)

    def to_json_dict(self) -> dict:
        return {
            "full_frame_yolo_call_count": self.full_frame_yolo_call_count,
            "roi_yolo_call_count": self.roi_yolo_call_count,
            "full_frame_input_pixel_area": self.full_frame_input_pixel_area,
            "roi_input_pixel_area": self.roi_input_pixel_area,
            "yolo_call_reduction": self.yolo_call_reduction,
            "input_pixel_area_reduction": self.input_pixel_area_reduction,
        }


def summarize_workload(full_frame_metrics: dict[str, Any], roi_metrics: dict[str, Any]) -> WorkloadSummary:
    return WorkloadSummary(
        full_frame_yolo_call_count=int(full_frame_metrics.get("yolo_call_count", 0)),
        roi_yolo_call_count=int(roi_metrics.get("yolo_call_count", 0)),
        full_frame_input_pixel_area=int(full_frame_metrics.get("yolo_input_pixel_area", 0)),
        roi_input_pixel_area=int(roi_metrics.get("yolo_input_pixel_area", 0)),
    )
