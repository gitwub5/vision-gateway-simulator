"""Shared annotation loader helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import GroundTruthAnnotation
from common.io import load_yaml_config, read_jsonl, write_jsonl
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


def load_annotation_config(config_path: str | Path) -> dict[str, Any] | None:
    config = load_yaml_config(config_path)
    annotations = config.get("annotations")
    return dict(annotations) if annotations else None


def read_ground_truth_jsonl(input_path: str | Path) -> list[GroundTruthAnnotation]:
    records: list[GroundTruthAnnotation] = []
    for data in read_jsonl(input_path):
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
    write_jsonl(records, output_path)


def dataset_frame_ids_by_file_name(dataset_config: DatasetConfig) -> dict[str, int]:
    image_paths = dataset_image_paths(dataset_config)
    return {
        image_path.name: dataset_config.start_frame + offset
        for offset, image_path in enumerate(image_paths)
    }


def dataset_frame_metadata_by_one_based_index(dataset_config: DatasetConfig) -> dict[int, tuple[int, str]]:
    image_paths = dataset_image_paths(dataset_config)
    return {
        dataset_config.start_frame + offset + 1: (dataset_config.start_frame + offset, image_path.name)
        for offset, image_path in enumerate(image_paths)
    }


def dataset_image_paths(dataset_config: DatasetConfig) -> list[Path]:
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


def coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def frame_in_dataset_range(frame_id: int, dataset_config: DatasetConfig) -> bool:
    if frame_id < dataset_config.start_frame:
        return False
    if dataset_config.frame_limit is None:
        return True
    return frame_id < dataset_config.start_frame + dataset_config.frame_limit
