"""Dataset annotation loaders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


class ConstructionSiteStaticCameraAnnotationLoader(AnnotationLoader):
    """Loads construction-site YOLO txt labels into dataset frame ids."""

    DEFAULT_CLASSES = (
        "Dump_truck",
        "Excavator",
        "Concrete_mixer_truck",
        "Skid_steer",
        "Tower_crane",
        "Truck_crane",
        "Truck",
        "Person",
    )

    def __init__(
        self,
        input_path: str | Path,
        dataset_config: DatasetConfig,
        class_names: list[str] | tuple[str, ...] | None = None,
        image_size: list[int] | tuple[int, int] | None = None,
    ) -> None:
        super().__init__(input_path)
        self.dataset_config = dataset_config
        self.class_names = tuple(class_names or self.DEFAULT_CLASSES)
        self.image_size = tuple(int(value) for value in image_size) if image_size else None

    def load(self) -> list[GroundTruthAnnotation]:
        if self.input_path is None:
            return []
        if not self.input_path.exists():
            raise FileNotFoundError(f"Annotation directory does not exist: {self.input_path}")

        gt_annotations: list[GroundTruthAnnotation] = []
        image_paths = _dataset_image_paths(self.dataset_config)
        for offset, image_path in enumerate(image_paths):
            label_path = self.input_path / f"{image_path.stem}.txt"
            if not label_path.exists():
                continue
            width, height = self.image_size or _read_image_size(image_path)
            frame_id = self.dataset_config.start_frame + offset
            for label_index, line in enumerate(label_path.read_text(encoding="utf-8").splitlines()):
                stripped = line.strip()
                if not stripped:
                    continue
                parts = stripped.split()
                if len(parts) != 5:
                    raise ValueError(f"Expected YOLO txt label with 5 columns in {label_path}: {line}")
                class_id = int(parts[0])
                x_center, y_center, box_width, box_height = [float(value) for value in parts[1:]]
                x1 = (x_center - box_width / 2.0) * width
                y1 = (y_center - box_height / 2.0) * height
                x2 = (x_center + box_width / 2.0) * width
                y2 = (y_center + box_height / 2.0) * height
                gt_annotations.append(
                    GroundTruthAnnotation(
                        camera_id=self.dataset_config.camera_id,
                        frame_id=frame_id,
                        class_id=class_id,
                        class_name=_class_name_for_id(class_id, self.class_names),
                        bbox_xyxy=[x1, y1, x2, y2],
                        annotation_id=f"{image_path.stem}_{label_index}",
                        image_id=image_path.stem,
                        file_name=image_path.name,
                    )
                )
        return gt_annotations


def create_annotation_loader(
    annotation_config: dict[str, Any] | None,
    dataset_config: DatasetConfig,
) -> AnnotationLoader | None:
    if not annotation_config or not annotation_config.get("enabled", True):
        return None

    annotation_type = str(annotation_config.get("type", "")).lower()
    input_path = annotation_config.get("input_path")
    if not input_path:
        raise ValueError("annotations.input_path is required when annotations are enabled")

    if annotation_type == "od_virat_tiny":
        return OdViratTinyAnnotationLoader(input_path, dataset_config)
    if annotation_type == "construction_site_static_camera_txt":
        return ConstructionSiteStaticCameraAnnotationLoader(
            input_path,
            dataset_config,
            class_names=annotation_config.get("classes"),
            image_size=annotation_config.get("image_size"),
        )
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


def _read_image_size(image_path: Path) -> tuple[int, int]:
    try:
        import cv2
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "OpenCV is required for reading image sizes from YOLO txt annotations. "
            "Install project dependencies with `pip install -r requirements.txt`."
        ) from exc
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not read image for annotation sizing: {image_path}")
    height, width = image.shape[:2]
    return width, height


def _class_name_for_id(class_id: int, class_names: tuple[str, ...]) -> str:
    return class_names[class_id] if class_id < len(class_names) else str(class_id)


def _require_yaml():
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyYAML is required for loading YAML config files. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return yaml
