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


def _require_yaml():
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyYAML is required for loading YAML config files. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return yaml
