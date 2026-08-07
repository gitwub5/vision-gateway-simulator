"""Dataset annotation loaders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from common import GroundTruthAnnotation
from data_loader.dataset_stream import (
    DEFAULT_IMAGE_EXTENSIONS,
    DatasetConfig,
    list_image_sequence_paths,
)


class AnnotationLoader:
    def __init__(self, input_path: str | Path | None = None) -> None:
        self.input_path = Path(input_path) if input_path else None

    def load(self) -> list[GroundTruthAnnotation]:
        if self.input_path is None:
            return []
        raise NotImplementedError("Dataset-specific annotation loading is not implemented yet.")


class OdViratTinyAnnotationLoader(AnnotationLoader):
    """Loads OD-VIRAT Tiny COCO-style annotations into dataset frame ids."""

    def __init__(self, input_path: str | Path, dataset_config: DatasetConfig) -> None:
        super().__init__(input_path)
        self.dataset_config = dataset_config

    def load(self) -> list[GroundTruthAnnotation]:
        if self.input_path is None:
            return []
        with self.input_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        categories = {
            int(category["id"]): str(category["name"])
            for category in data.get("categories", [])
        }
        frame_ids_by_file_name = _dataset_frame_ids_by_file_name(self.dataset_config)
        annotations_by_image_id: dict[int | str, list[dict[str, Any]]] = {}
        for annotation in data.get("annotations", []):
            annotations_by_image_id.setdefault(annotation["image_id"], []).append(annotation)

        gt_annotations: list[GroundTruthAnnotation] = []
        for image in data.get("images", []):
            file_name = str(image["file_name"])
            if file_name not in frame_ids_by_file_name:
                continue
            frame_id = frame_ids_by_file_name[file_name]
            image_id = image["id"]
            for annotation in annotations_by_image_id.get(image_id, []):
                x, y, width, height = [float(value) for value in annotation["bbox"]]
                category_id = int(annotation["category_id"])
                gt_annotations.append(
                    GroundTruthAnnotation(
                        camera_id=self.dataset_config.camera_id,
                        frame_id=frame_id,
                        class_id=category_id,
                        class_name=categories.get(category_id, str(category_id)),
                        bbox_xyxy=[x, y, x + width, y + height],
                        annotation_id=annotation.get("id", ""),
                        image_id=image_id,
                        file_name=file_name,
                        iscrowd=int(annotation.get("iscrowd", 0) or 0),
                    )
                )
        return gt_annotations


class UaDetracAnnotationLoader(AnnotationLoader):
    """Loads UA-DETRAC sequence XML annotations into dataset frame ids."""

    VEHICLE_CLASS_MAP = {
        "car": (2, "car"),
        "bus": (5, "bus"),
        "van": (2, "car"),
        "others": (7, "truck"),
        "other": (7, "truck"),
        "truck": (7, "truck"),
    }

    def __init__(self, input_path: str | Path, dataset_config: DatasetConfig) -> None:
        super().__init__(input_path)
        self.dataset_config = dataset_config

    def load(self) -> list[GroundTruthAnnotation]:
        if self.input_path is None:
            return []
        annotation_path = self._resolve_annotation_path()
        root = ET.parse(annotation_path).getroot()
        frame_metadata = _dataset_frame_metadata_by_one_based_index(self.dataset_config)

        annotations: list[GroundTruthAnnotation] = []
        sequence_name = annotation_path.stem
        for frame in root.findall(".//frame"):
            frame_num = int(frame.attrib.get("num", "0"))
            if frame_num not in frame_metadata:
                continue
            frame_id, file_name = frame_metadata[frame_num]
            for target in frame.findall("./target_list/target"):
                box = target.find("box")
                if box is None:
                    continue
                x = float(box.attrib["left"])
                y = float(box.attrib["top"])
                width = float(box.attrib["width"])
                height = float(box.attrib["height"])
                vehicle_type = _ua_detrac_vehicle_type(target)
                class_id, class_name = self.VEHICLE_CLASS_MAP.get(vehicle_type, (7, "truck"))
                target_id = target.attrib.get("id", "")
                annotations.append(
                    GroundTruthAnnotation(
                        camera_id=self.dataset_config.camera_id,
                        frame_id=frame_id,
                        class_id=class_id,
                        class_name=class_name,
                        bbox_xyxy=[x, y, x + width, y + height],
                        annotation_id=f"{sequence_name}_f{frame_num:05d}_target_{target_id}",
                        image_id=frame_num,
                        file_name=file_name,
                    )
                )
        return annotations

    def _resolve_annotation_path(self) -> Path:
        if self.input_path is None:
            raise FileNotFoundError("UA-DETRAC annotation path is not configured")
        if self.input_path.is_file():
            return self.input_path
        if self.input_path.is_dir():
            candidate = self.input_path / f"{self.dataset_config.camera_id}.xml"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"UA-DETRAC annotation XML does not exist: {self.input_path}")


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
        with self.input_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        records = _physicalai_official_frame_keyed_records(data, self.camera_id, self.dataset_config)
        if records is None:
            records = _iter_physicalai_annotation_candidates(data)

        annotations: list[GroundTruthAnnotation] = []
        for index, raw in enumerate(records):
            if not _matches_camera(raw.get("camera_id"), self.camera_id):
                continue
            frame_id = _coerce_int(raw.get("frame_id"))
            if frame_id is None or not _frame_in_dataset_range(frame_id, self.dataset_config):
                continue
            bbox = _parse_physicalai_bbox(raw.get("bbox"), self.bbox_format)
            if bbox is None:
                continue

            class_name = _normalize_physicalai_class_name(raw.get("class_name"))
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


def create_annotation_loader(
    annotation_config: dict[str, Any] | None,
    dataset_config: DatasetConfig,
) -> AnnotationLoader | None:
    if not annotation_config or not annotation_config.get("enabled", True):
        return None

    annotation_type = str(annotation_config.get("type", "")).lower()
    if annotation_type in {"", "none", "null"}:
        return None
    input_path = annotation_config.get("input_path")
    if not input_path:
        raise ValueError("annotations.input_path is required when annotations are enabled")

    if annotation_type == "od_virat_tiny":
        return OdViratTinyAnnotationLoader(input_path, dataset_config)
    if annotation_type == "ua_detrac_xml":
        return UaDetracAnnotationLoader(input_path, dataset_config)
    if annotation_type == "physicalai_smartspaces_json":
        return PhysicalAiSmartSpacesAnnotationLoader(input_path, dataset_config, annotation_config)
    raise ValueError(f"Unsupported annotations.type: {annotation_type}")


def load_annotation_config(config_path: str | Path) -> dict[str, Any] | None:
    yaml = _require_yaml()
    with Path(config_path).open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    annotations = config.get("annotations")
    return dict(annotations) if annotations else None


def read_ground_truth_jsonl(input_path: str | Path) -> list[GroundTruthAnnotation]:
    records: list[GroundTruthAnnotation] = []
    with Path(input_path).open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            data = json.loads(stripped)
            records.append(
                GroundTruthAnnotation(
                    camera_id=str(data["camera_id"]),
                    frame_id=int(data["frame_id"]),
                    class_id=int(data["class_id"]),
                    class_name=str(data["class_name"]),
                    bbox_xyxy=[float(value) for value in data["bbox_xyxy"]],
                    annotation_id=data["annotation_id"],
                    image_id=data["image_id"],
                    file_name=str(data["file_name"]),
                    source=str(data.get("source", "ground_truth")),
                    iscrowd=int(data.get("iscrowd", 0) or 0),
                )
            )
    return records


def write_ground_truth_jsonl(records: list[GroundTruthAnnotation], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record.to_json_dict(), ensure_ascii=False) + "\n")


def _dataset_frame_ids_by_file_name(dataset_config: DatasetConfig) -> dict[str, int]:
    image_paths = _dataset_image_paths(dataset_config)
    return {
        image_path.name: dataset_config.start_frame + offset
        for offset, image_path in enumerate(image_paths)
    }


def _dataset_frame_metadata_by_one_based_index(dataset_config: DatasetConfig) -> dict[int, tuple[int, str]]:
    image_paths = _dataset_image_paths(dataset_config)
    return {
        dataset_config.start_frame + offset + 1: (dataset_config.start_frame + offset, image_path.name)
        for offset, image_path in enumerate(image_paths)
    }


def _dataset_image_paths(dataset_config: DatasetConfig) -> list[Path]:
    if dataset_config.type not in {"image_sequence", "images"}:
        raise ValueError("Annotation mapping requires an image sequence dataset")
    if not dataset_config.input_path.exists():
        raise FileNotFoundError(f"Image sequence directory does not exist: {dataset_config.input_path}")

    extensions = dataset_config.image_extensions or DEFAULT_IMAGE_EXTENSIONS
    image_paths = list_image_sequence_paths(dataset_config.input_path, extensions)
    image_paths = image_paths[dataset_config.start_frame :]
    if dataset_config.frame_limit is not None:
        image_paths = image_paths[: dataset_config.frame_limit]
    return image_paths


def _ua_detrac_vehicle_type(target: ET.Element) -> str:
    attribute = target.find("attribute")
    if attribute is None:
        return "others"
    return str(attribute.attrib.get("vehicle_type", "others")).strip().lower()


def _iter_physicalai_annotation_candidates(data: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    _walk_physicalai_json(data, {}, candidates)
    return candidates


def _physicalai_official_frame_keyed_records(
    data: Any,
    camera_id: str,
    dataset_config: DatasetConfig,
) -> list[dict[str, Any]] | None:
    if not isinstance(data, dict) or not all(str(key).isdigit() for key in data):
        return None

    records: list[dict[str, Any]] = []
    for frame_id, objects in data.items():
        frame_number = _coerce_int(frame_id)
        if frame_number is None or not _frame_in_dataset_range(frame_number, dataset_config):
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
                if not _matches_camera(box_camera_id, camera_id):
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


def _walk_physicalai_json(value: Any, context: dict[str, Any], candidates: list[dict[str, Any]]) -> None:
    if isinstance(value, list):
        for item in value:
            _walk_physicalai_json(item, context, candidates)
        return
    if not isinstance(value, dict):
        return

    current = dict(context)
    _merge_physicalai_context(current, value)
    _collect_physicalai_visible_boxes(value, current, candidates)
    bbox = _extract_physicalai_bbox_value(value)
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
        if _looks_like_physicalai_camera_id(key):
            child_context["camera_id"] = key
        if str(key).isdigit():
            child_context["frame_id"] = key
        _walk_physicalai_json(child, child_context, candidates)


def _collect_physicalai_visible_boxes(
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


def _merge_physicalai_context(context: dict[str, Any], value: dict[str, Any]) -> None:
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


def _extract_physicalai_bbox_value(value: dict[str, Any]) -> Any | None:
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


def _parse_physicalai_bbox(value: Any, bbox_format: str) -> list[float] | None:
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


def _normalize_physicalai_class_name(value: Any) -> str:
    raw = str(value or "object").strip().lower().replace("_", " ")
    normalized = PhysicalAiSmartSpacesAnnotationLoader.CLASS_NAME_ALIASES.get(raw, raw)
    return normalized.replace(" ", "_")


def _matches_camera(value: Any, camera_id: str) -> bool:
    if value is None:
        return False
    normalized_value = str(value).strip().lower()
    normalized_camera_id = camera_id.strip().lower()
    return normalized_value == normalized_camera_id or normalized_value.endswith(f"/{normalized_camera_id}")


def _looks_like_physicalai_camera_id(value: Any) -> bool:
    text = str(value)
    return text.lower().startswith("camera_")


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _frame_in_dataset_range(frame_id: int, dataset_config: DatasetConfig) -> bool:
    if frame_id < dataset_config.start_frame:
        return False
    if dataset_config.frame_limit is None:
        return True
    return frame_id < dataset_config.start_frame + dataset_config.frame_limit


def _require_yaml():
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyYAML is required for loading YAML config files. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return yaml
