"""ROI crop YOLO runner and metadata readers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

from common import Detection, FramePacket, FrameSize, GateFrameMetadata, ROI, ROIMetadata, TriggerType
from common.io import read_jsonl, write_json
from common.records import frame_key
from gpu_inference.coordinate_restore import restore_xyxy_from_crop
from gpu_inference.yolo_full_frame import YoloConfig


FULL_FRAME_CHECK_SOURCE = "roi_yolo_full_frame_check"
ROI_YOLO_SOURCE = "roi_yolo"


@dataclass
class RoiYoloMetrics:
    frame_count: int = 0
    roi_record_count: int = 0
    roi_yolo_call_count: int = 0
    full_frame_check_call_count: int = 0
    yolo_call_count: int = 0
    roi_input_pixel_area: int = 0
    full_frame_input_pixel_area: int = 0
    yolo_input_pixel_area: int = 0
    latency_ms: list[float] = field(default_factory=list)
    detection_count: int = 0
    model: str = ""
    image_size: int = 640
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    classes: tuple[str, ...] = field(default_factory=tuple)

    def to_json_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["classes"] = list(self.classes)
        values["average_latency_ms"] = (
            sum(self.latency_ms) / len(self.latency_ms) if self.latency_ms else 0.0
        )
        values["average_roi_count"] = (
            self.roi_record_count / self.frame_count if self.frame_count else 0.0
        )
        return values


class RoiYoloRunner:
    def __init__(
        self,
        model_path: str,
        image_size: int = 640,
        confidence_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        classes: Iterable[str] | None = None,
        model: Any | None = None,
    ) -> None:
        self.model_path = model_path
        self.image_size = image_size
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.classes = tuple(classes or ())
        self._model = model
        self.last_metrics = RoiYoloMetrics(
            model=model_path,
            image_size=image_size,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
            classes=self.classes,
        )

    @classmethod
    def from_config(cls, config: YoloConfig, model: Any | None = None) -> "RoiYoloRunner":
        return cls(
            model_path=config.model,
            image_size=config.image_size,
            confidence_threshold=config.confidence_threshold,
            iou_threshold=config.iou_threshold,
            classes=config.classes,
            model=model,
        )

    def load(self):
        from ultralytics import YOLO

        self._model = YOLO(self.model_path)
        return self

    def run(
        self,
        frames: Iterable[FramePacket],
        roi_records: Iterable[ROIMetadata],
        frame_records: Iterable[GateFrameMetadata] | None = None,
        include_full_frame_checks: bool = True,
    ) -> list[Detection]:
        if self._model is None:
            self.load()

        roi_by_frame = _group_roi_records(roi_records)
        frame_decision_by_frame = _index_frame_records(frame_records or [])
        detections: list[Detection] = []
        metrics = RoiYoloMetrics(
            model=self.model_path,
            image_size=self.image_size,
            confidence_threshold=self.confidence_threshold,
            iou_threshold=self.iou_threshold,
            classes=self.classes,
        )

        for packet in frames:
            key = frame_key(packet.camera_id, packet.frame_id)
            frame_rois = roi_by_frame.get(key, [])
            frame_decision = frame_decision_by_frame.get(key)
            metrics.frame_count += 1
            metrics.roi_record_count += len(frame_rois)

            if include_full_frame_checks and frame_decision and frame_decision.should_run_full_frame:
                detections.extend(self._run_full_frame_check(packet, metrics))

            for roi_record in frame_rois:
                detections.extend(self._run_roi_crop(packet, roi_record, metrics))

        metrics.yolo_call_count = metrics.roi_yolo_call_count + metrics.full_frame_check_call_count
        metrics.yolo_input_pixel_area = (
            metrics.roi_input_pixel_area + metrics.full_frame_input_pixel_area
        )
        metrics.detection_count = len(detections)
        self.last_metrics = metrics
        return detections

    def _run_full_frame_check(
        self, packet: FramePacket, metrics: RoiYoloMetrics
    ) -> list[Detection]:
        started = perf_counter()
        results = self._predict(packet.frame)
        metrics.latency_ms.append((perf_counter() - started) * 1000.0)
        metrics.full_frame_check_call_count += 1
        metrics.full_frame_input_pixel_area += packet.original_size.area()

        detections: list[Detection] = []
        for result in results:
            detections.extend(
                self._detections_from_result(
                    packet=packet,
                    result=result,
                    source=FULL_FRAME_CHECK_SOURCE,
                    roi_record=None,
                )
            )
        return detections

    def _run_roi_crop(
        self, packet: FramePacket, roi_record: ROIMetadata, metrics: RoiYoloMetrics
    ) -> list[Detection]:
        crop = crop_frame(packet, roi_record.roi)
        started = perf_counter()
        results = self._predict(crop)
        metrics.latency_ms.append((perf_counter() - started) * 1000.0)
        metrics.roi_yolo_call_count += 1
        metrics.roi_input_pixel_area += clipped_roi_area(packet, roi_record.roi)

        detections: list[Detection] = []
        for result in results:
            detections.extend(
                self._detections_from_result(
                    packet=packet,
                    result=result,
                    source=ROI_YOLO_SOURCE,
                    roi_record=roi_record,
                )
            )
        return detections

    def _predict(self, frame: Any) -> Any:
        return self._model.predict(
            frame,
            imgsz=self.image_size,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            verbose=False,
        )

    def _detections_from_result(
        self,
        packet: FramePacket,
        result: Any,
        source: str,
        roi_record: ROIMetadata | None,
    ) -> list[Detection]:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        xyxy_values = _to_list(getattr(boxes, "xyxy", []))
        confidence_values = _to_list(getattr(boxes, "conf", []))
        class_values = _to_list(getattr(boxes, "cls", []))
        names = getattr(result, "names", {}) or {}
        allowed_classes = set(self.classes)

        detections: list[Detection] = []
        for bbox_xyxy, confidence, class_id_value in zip(
            xyxy_values, confidence_values, class_values, strict=False
        ):
            class_id = int(class_id_value)
            class_name = str(names.get(class_id, class_id))
            if allowed_classes and class_name not in allowed_classes:
                continue

            bbox = [float(value) for value in bbox_xyxy]
            roi_id = None
            if roi_record is not None:
                bbox = restore_xyxy_from_crop(bbox, roi_record.roi)
                roi_id = roi_record.roi_id

            detections.append(
                Detection(
                    camera_id=packet.camera_id,
                    frame_id=packet.frame_id,
                    class_id=class_id,
                    class_name=class_name,
                    confidence=float(confidence),
                    bbox_xyxy=bbox,
                    source=source,
                    roi_id=roi_id,
                )
            )
        return detections


def crop_frame(packet: FramePacket, roi: ROI) -> Any:
    x1 = max(0, roi.x)
    y1 = max(0, roi.y)
    x2 = min(packet.original_size.width, roi.x + roi.w)
    y2 = min(packet.original_size.height, roi.y + roi.h)
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid ROI crop for frame {packet.frame_id}: {roi}")
    return packet.frame[y1:y2, x1:x2]


def clipped_roi_area(packet: FramePacket, roi: ROI) -> int:
    x1 = max(0, roi.x)
    y1 = max(0, roi.y)
    x2 = min(packet.original_size.width, roi.x + roi.w)
    y2 = min(packet.original_size.height, roi.y + roi.h)
    return max(0, x2 - x1) * max(0, y2 - y1)


def read_roi_metadata_jsonl(input_path: str | Path) -> list[ROIMetadata]:
    records: list[ROIMetadata] = []
    for data in read_jsonl(input_path):
        original_width, original_height = data["original_frame_size"]
        analysis_width, analysis_height = data["analysis_frame_size"]
        x, y, w, h = data["roi_xywh"]
        records.append(
            ROIMetadata(
                camera_id=str(data["camera_id"]),
                frame_id=int(data["frame_id"]),
                timestamp=float(data["timestamp"]),
                roi_id=str(data["roi_id"]),
                original_frame_size=FrameSize(width=int(original_width), height=int(original_height)),
                analysis_frame_size=FrameSize(width=int(analysis_width), height=int(analysis_height)),
                roi=ROI(
                    x=int(x),
                    y=int(y),
                    w=int(w),
                    h=int(h),
                    score=float(data.get("score", 1.0)),
                    coord_system="original_frame",
                ),
                source=str(data.get("source", "rule_based_roi_generator")),
                trigger_type=TriggerType(str(data.get("trigger_type", TriggerType.ROI.value))),
            )
        )
    return records


def read_gate_frame_metadata_jsonl(input_path: str | Path) -> list[GateFrameMetadata]:
    records: list[GateFrameMetadata] = []
    for data in read_jsonl(input_path):
        original_width, original_height = data["original_frame_size"]
        analysis_width, analysis_height = data["analysis_frame_size"]
        records.append(
            GateFrameMetadata(
                camera_id=str(data["camera_id"]),
                frame_id=int(data["frame_id"]),
                timestamp=float(data["timestamp"]),
                trigger_type=TriggerType(str(data["trigger_type"])),
                roi_count=int(data["roi_count"]),
                should_run_full_frame=bool(data["should_run_full_frame"]),
                gate_latency_ms=float(data["gate_latency_ms"]),
                original_frame_size=FrameSize(width=int(original_width), height=int(original_height)),
                analysis_frame_size=FrameSize(width=int(analysis_width), height=int(analysis_height)),
                source=str(data.get("source", "rule_based_roi_generator")),
            )
        )
    return records


def write_roi_metrics_json(metrics: RoiYoloMetrics, output_path: str | Path) -> None:
    write_json(metrics.to_json_dict(), output_path)


def _group_roi_records(records: Iterable[ROIMetadata]) -> dict[tuple[str, int], list[ROIMetadata]]:
    grouped: dict[tuple[str, int], list[ROIMetadata]] = {}
    for record in records:
        grouped.setdefault(frame_key(record.camera_id, record.frame_id), []).append(record)
    return grouped


def _index_frame_records(records: Iterable[GateFrameMetadata]) -> dict[tuple[str, int], GateFrameMetadata]:
    return {frame_key(record.camera_id, record.frame_id): record for record in records}


def _to_list(value: Any) -> list[Any]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value)
