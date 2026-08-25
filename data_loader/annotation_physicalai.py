"""PhysicalAI Smart Spaces annotation loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import GroundTruthAnnotation
from common.io import read_json
from data_loader.annotation_common import (
    AnnotationLoader,
    coerce_int,
    frame_in_dataset_range,
)
from data_loader.dataset_stream import DatasetConfig


class PhysicalAiSmartSpacesAnnotationLoader(AnnotationLoader):
    """Loads NVIDIA PhysicalAI Smart Spaces 2D camera annotations.

    The upstream JSON is scene-level and can contain annotations for multiple
    cameras. This loader accepts common frame/object/camera nesting patterns and
    filters records to the dataset camera id by default.
    """

    CLASS_ID_MAP = {
        "person": 0,
        "human": 0,
        "worker": 0,
        "car": 2,
        "truck": 7,
        "forklift": 1001,
        "pallet_truck": 1002,
        "pallet jack": 1002,
        "robot": 1003,
        "amr": 1003,
    }

    CLASS_NAME_ALIASES = {
        "human": "person",
        "worker": "person",
        "pallet jack": "pallet_truck",
        "palletjack": "pallet_truck",
        "pallettruck": "pallet_truck",
        "pallet-truck": "pallet_truck",
        "autonomous mobile robot": "robot",
        "mobile robot": "robot",
    }

    def __init__(
        self,
        input_path: str | Path,
        dataset_config: DatasetConfig,
        annotation_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(input_path)
        self.dataset_config = dataset_config
        self.annotation_config = annotation_config or {}
        self.camera_id = str(self.annotation_config.get("camera_id") or dataset_config.camera_id)
        self.bbox_format = str(self.annotation_config.get("bbox_format", "xyxy")).lower()

    def load(self) -> list[GroundTruthAnnotation]:
        if self.input_path is None:
            return []
        data = read_json(self.input_path)

        records = physicalai_official_frame_keyed_records(data, self.camera_id, self.dataset_config)
        if records is None:
            records = iter_physicalai_annotation_candidates(data)

        annotations: list[GroundTruthAnnotation] = []
        for index, raw in enumerate(records):
            if not matches_camera(raw.get("camera_id"), self.camera_id):
                continue
            frame_id = coerce_int(raw.get("frame_id"))
            if frame_id is None or not frame_in_dataset_range(frame_id, self.dataset_config):
                continue
            bbox = parse_physicalai_bbox(raw.get("bbox"), self.bbox_format)
            if bbox is None:
                continue

            class_name = normalize_physicalai_class_name(raw.get("class_name"))
            annotations.append(
                GroundTruthAnnotation(
                    camera_id=self.dataset_config.camera_id,
                    frame_id=frame_id,
                    class_id=self.CLASS_ID_MAP.get(class_name, 9999),
                    class_name=class_name,
                    bbox_xyxy=bbox,
                    annotation_id=raw.get("annotation_id") or f"physicalai_{self.camera_id}_f{frame_id:06d}_{index}",
                    image_id=raw.get("image_id") or frame_id,
                    file_name=str(raw.get("file_name") or f"{self.dataset_config.input_path.name}:frame_{frame_id:06d}"),
                )
            )
        return annotations


def iter_physicalai_annotation_candidates(data: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    walk_physicalai_json(data, {}, candidates)
    return candidates


def physicalai_official_frame_keyed_records(
    data: Any,
    camera_id: str,
    dataset_config: DatasetConfig,
) -> list[dict[str, Any]] | None:
    if not isinstance(data, dict) or not all(str(key).isdigit() for key in data):
        return None

    records: list[dict[str, Any]] = []
    for frame_id, objects in data.items():
        frame_number = coerce_int(frame_id)
        if frame_number is None or not frame_in_dataset_range(frame_number, dataset_config):
            continue
        if not isinstance(objects, list):
            return None
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            visible_boxes = obj.get("2d_bounding_box_visible") or obj.get("2d bounding box visible")
            if not isinstance(visible_boxes, dict):
                continue
            class_name = obj.get("class_name") or obj.get("object_type") or obj.get("object type")
            annotation_id = obj.get("annotation_id") or obj.get("object_id") or obj.get("object id")
            for box_camera_id, bbox in visible_boxes.items():
                if not matches_camera(box_camera_id, camera_id):
                    continue
                records.append(
                    {
                        "frame_id": frame_number,
                        "camera_id": box_camera_id,
                        "class_name": class_name,
                        "annotation_id": annotation_id,
                        "bbox": bbox,
                    }
                )
    return records


def walk_physicalai_json(value: Any, context: dict[str, Any], candidates: list[dict[str, Any]]) -> None:
    if isinstance(value, list):
        for item in value:
            walk_physicalai_json(item, context, candidates)
        return
    if not isinstance(value, dict):
        return

    current = dict(context)
    merge_physicalai_context(current, value)
    collect_physicalai_visible_boxes(value, current, candidates)
    bbox = extract_physicalai_bbox_value(value)
    if bbox is not None and current.get("frame_id") is not None:
        candidate = dict(current)
        candidate["bbox"] = bbox
        candidates.append(candidate)

    for key, child in value.items():
        if key in {
            "bbox_xyxy",
            "bbox2d",
            "bbox",
            "bounding_box",
            "box",
            "rect",
            "2d_bounding_box_visible",
            "2d bounding box visible",
        }:
            continue
        child_context = dict(current)
        if looks_like_physicalai_camera_id(key):
            child_context["camera_id"] = key
        if str(key).isdigit():
            child_context["frame_id"] = key
        walk_physicalai_json(child, child_context, candidates)


def collect_physicalai_visible_boxes(
    value: dict[str, Any],
    context: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> None:
    visible_boxes = value.get("2d_bounding_box_visible") or value.get("2d bounding box visible")
    if not isinstance(visible_boxes, dict) or context.get("frame_id") is None:
        return
    for camera_id, bbox in visible_boxes.items():
        candidate = dict(context)
        candidate["camera_id"] = camera_id
        candidate["bbox"] = bbox
        candidates.append(candidate)


def merge_physicalai_context(context: dict[str, Any], value: dict[str, Any]) -> None:
    for key in ("frame_id", "frame", "frame_index", "frame_idx", "frameId", "frameNumber", "frame_number"):
        if key in value:
            context["frame_id"] = value[key]
            break
    for key in ("camera_id", "camera", "cameraId", "camera_name", "sensor_id", "sensor"):
        if key in value:
            context["camera_id"] = value[key]
            break
    for key in (
        "class_name",
        "class",
        "category",
        "label",
        "type",
        "object_class",
        "object_type",
        "object type",
    ):
        if key in value:
            context["class_name"] = value[key]
            break
    for key in ("annotation_id", "id", "object_id", "object id", "track_id", "instance_id"):
        if key in value:
            context["annotation_id"] = value[key]
            break
    for key in ("image_id", "imageId"):
        if key in value:
            context["image_id"] = value[key]
            break
    for key in ("file_name", "filename", "file"):
        if key in value:
            context["file_name"] = value[key]
            break


def extract_physicalai_bbox_value(value: dict[str, Any]) -> Any | None:
    for key in ("bbox_xyxy", "bbox2d", "bbox", "bounding_box", "box", "rect"):
        if key in value:
            return value[key]
    if {"x1", "y1", "x2", "y2"}.issubset(value):
        return {key: value[key] for key in ("x1", "y1", "x2", "y2")}
    if {"left", "top", "width", "height"}.issubset(value):
        return {key: value[key] for key in ("left", "top", "width", "height")}
    if {"x", "y", "w", "h"}.issubset(value):
        return {key: value[key] for key in ("x", "y", "w", "h")}
    return None


def parse_physicalai_bbox(value: Any, bbox_format: str) -> list[float] | None:
    if isinstance(value, dict):
        if {"x1", "y1", "x2", "y2"}.issubset(value):
            return [float(value["x1"]), float(value["y1"]), float(value["x2"]), float(value["y2"])]
        if {"left", "top", "width", "height"}.issubset(value):
            x = float(value["left"])
            y = float(value["top"])
            return [x, y, x + float(value["width"]), y + float(value["height"])]
        if {"x", "y", "w", "h"}.issubset(value):
            x = float(value["x"])
            y = float(value["y"])
            return [x, y, x + float(value["w"]), y + float(value["h"])]
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        a, b, c, d = [float(item) for item in value[:4]]
        if bbox_format == "xywh":
            return [a, b, a + c, b + d]
        return [a, b, c, d]
    return None


def normalize_physicalai_class_name(value: Any) -> str:
    raw = str(value or "object").strip().lower().replace("_", " ")
    normalized = PhysicalAiSmartSpacesAnnotationLoader.CLASS_NAME_ALIASES.get(raw, raw)
    return normalized.replace(" ", "_")


def matches_camera(value: Any, camera_id: str) -> bool:
    if value is None:
        return False
    normalized_value = str(value).strip().lower()
    normalized_camera_id = camera_id.strip().lower()
    return normalized_value == normalized_camera_id or normalized_value.endswith(f"/{normalized_camera_id}")


def looks_like_physicalai_camera_id(value: Any) -> bool:
    text = str(value)
    return text.lower().startswith("camera_")
