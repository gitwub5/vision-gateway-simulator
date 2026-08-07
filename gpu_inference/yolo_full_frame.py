"""Full-frame YOLO baseline runner and serialization helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from common import Detection, FramePacket


@dataclass(frozen=True)
class YoloConfig:
    model: str = "yolov8n.pt"
    image_size: int = 640
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    classes: tuple[str, ...] = ("person", "car", "truck", "bus")

    @classmethod
    def from_mapping(cls, config: dict[str, Any]) -> "YoloConfig":
        yolo = config.get("yolo", config)
        return cls(
            model=str(yolo.get("model", cls.model)),
            image_size=int(yolo.get("image_size", cls.image_size)),
            confidence_threshold=float(
                yolo.get("confidence_threshold", cls.confidence_threshold)
            ),
            iou_threshold=float(yolo.get("iou_threshold", cls.iou_threshold)),
            classes=tuple(str(name) for name in yolo.get("classes", cls.classes)),
        )


@dataclass(frozen=True)
class YoloOutputPaths:
    full_frame_detections: Path = Path("outputs/detections/full_frame.jsonl")
    roi_detections: Path = Path("outputs/detections/roi_yolo.jsonl")
    full_frame_metrics: Path = Path("outputs/reports/full_frame_metrics.json")
    roi_metrics: Path = Path("outputs/reports/roi_yolo_metrics.json")

    @classmethod
    def from_mapping(cls, config: dict[str, Any]) -> "YoloOutputPaths":
        outputs = config.get("outputs", {})
        return cls(
            full_frame_detections=Path(
                outputs.get("full_frame_detections", cls.full_frame_detections)
            ),
            roi_detections=Path(outputs.get("roi_detections", cls.roi_detections)),
            full_frame_metrics=Path(outputs.get("full_frame_metrics", cls.full_frame_metrics)),
            roi_metrics=Path(outputs.get("roi_metrics", cls.roi_metrics)),
        )


@dataclass
class FullFrameYoloMetrics:
    frame_count: int = 0
    yolo_call_count: int = 0
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
        return values


class FullFrameYoloRunner:
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
        self.last_metrics = FullFrameYoloMetrics(
            model=model_path,
            image_size=image_size,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
            classes=self.classes,
        )

    @classmethod
    def from_config(cls, config: YoloConfig, model: Any | None = None) -> "FullFrameYoloRunner":
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

    def run(self, frames: Iterable[FramePacket]) -> list[Detection]:
        if self._model is None:
            self.load()

        detections: list[Detection] = []
        metrics = FullFrameYoloMetrics(
            model=self.model_path,
            image_size=self.image_size,
            confidence_threshold=self.confidence_threshold,
            iou_threshold=self.iou_threshold,
            classes=self.classes,
        )

        for packet in frames:
            started = perf_counter()
            results = self._model.predict(
                packet.frame,
                imgsz=self.image_size,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                verbose=False,
            )
            metrics.latency_ms.append((perf_counter() - started) * 1000.0)
            metrics.frame_count += 1
            metrics.yolo_call_count += 1
            metrics.yolo_input_pixel_area += packet.original_size.area()

            for result in results:
                detections.extend(self._detections_from_result(packet, result))

        metrics.detection_count = len(detections)
        self.last_metrics = metrics
        return detections

    def _detections_from_result(self, packet: FramePacket, result: Any) -> list[Detection]:
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

            detections.append(
                Detection(
                    camera_id=packet.camera_id,
                    frame_id=packet.frame_id,
                    class_id=class_id,
                    class_name=class_name,
                    confidence=float(confidence),
                    bbox_xyxy=[float(value) for value in bbox_xyxy],
                    source="full_frame_yolo",
                    roi_id=None,
                )
            )
        return detections


def load_model_config(config_path: str | Path) -> tuple[YoloConfig, YoloOutputPaths]:
    yaml = _require_yaml()
    with Path(config_path).open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    return YoloConfig.from_mapping(config), YoloOutputPaths.from_mapping(config)


def load_yolo_config(config_path: str | Path) -> tuple[YoloConfig, YoloOutputPaths]:
    return load_model_config(config_path)


def write_detection_jsonl(detections: Iterable[Detection], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for detection in detections:
            file.write(json.dumps(detection.to_json_dict(), ensure_ascii=False) + "\n")


def write_metrics_json(metrics: FullFrameYoloMetrics, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(metrics.to_json_dict(), file, ensure_ascii=False, indent=2)
        file.write("\n")


def _to_list(value: Any) -> list[Any]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value)


def _require_yaml():
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyYAML is required for loading YAML config files. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return yaml
