"""OD-VIRAT Tiny annotation loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import GroundTruthAnnotation
from common.io import read_json
from data_loader.annotation_common import AnnotationLoader, dataset_frame_ids_by_file_name
from data_loader.dataset_stream import DatasetConfig


class OdViratTinyAnnotationLoader(AnnotationLoader):
    """Loads OD-VIRAT Tiny COCO-style annotations into dataset frame ids."""

    def __init__(self, input_path: str | Path, dataset_config: DatasetConfig) -> None:
        super().__init__(input_path)
        self.dataset_config = dataset_config

    def load(self) -> list[GroundTruthAnnotation]:
        if self.input_path is None:
            return []
        data = read_json(self.input_path)

        categories = {
            int(category["id"]): str(category["name"])
            for category in data.get("categories", [])
        }
        frame_ids_by_file_name = dataset_frame_ids_by_file_name(self.dataset_config)
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
