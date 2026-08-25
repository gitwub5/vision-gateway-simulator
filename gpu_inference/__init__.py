"""GPU inference adapters."""

from gpu_inference.yolo_full_frame import (
    FullFrameYoloMetrics,
    FullFrameYoloRunner,
    YoloConfig,
    YoloOutputPaths,
    load_model_config,
    load_yolo_config,
    write_detection_jsonl,
    write_metrics_json,
)
from gpu_inference.yolo_roi import (
    RoiYoloMetrics,
    RoiYoloRunner,
    crop_frame,
    read_gate_frame_metadata_jsonl,
    read_roi_metadata_jsonl,
    write_roi_metrics_json,
)

__all__ = [
    "FullFrameYoloMetrics",
    "FullFrameYoloRunner",
    "RoiYoloMetrics",
    "RoiYoloRunner",
    "YoloConfig",
    "YoloOutputPaths",
    "crop_frame",
    "load_model_config",
    "load_yolo_config",
    "read_gate_frame_metadata_jsonl",
    "read_roi_metadata_jsonl",
    "write_detection_jsonl",
    "write_metrics_json",
    "write_roi_metrics_json",
]
