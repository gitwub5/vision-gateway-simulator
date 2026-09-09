"""Dataset annotation loader facade.

Dataset-specific parsing lives in smaller modules, while this file preserves the
original public import surface used by experiments and tests.
"""

from __future__ import annotations

from typing import Any

from data_loader.annotation_common import (
    AnnotationLoader,
    load_annotation_config,
    read_ground_truth_jsonl,
    write_ground_truth_jsonl,
)
from data_loader.annotation_mall import MallDatasetAnnotationLoader
from data_loader.annotation_motchallenge import MotChallengeAnnotationLoader
from data_loader.annotation_od_virat import OdViratTinyAnnotationLoader
from data_loader.annotation_physicalai import PhysicalAiSmartSpacesAnnotationLoader
from data_loader.annotation_ua_detrac import UaDetracAnnotationLoader
from data_loader.annotation_visdrone import VisDroneVidAnnotationLoader
from data_loader.dataset_stream import DatasetConfig


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
    if annotation_type in {"motchallenge_gt", "motchallenge"}:
        return MotChallengeAnnotationLoader(input_path, dataset_config)
    if annotation_type in {"mall_dataset_head_points", "mall_head_points"}:
        return MallDatasetAnnotationLoader(input_path, dataset_config, annotation_config)
    if annotation_type in {"visdrone_vid", "visdrone"}:
        return VisDroneVidAnnotationLoader(input_path, dataset_config)
    raise ValueError(f"Unsupported annotations.type: {annotation_type}")


__all__ = [
    "AnnotationLoader",
    "MallDatasetAnnotationLoader",
    "MotChallengeAnnotationLoader",
    "OdViratTinyAnnotationLoader",
    "PhysicalAiSmartSpacesAnnotationLoader",
    "UaDetracAnnotationLoader",
    "VisDroneVidAnnotationLoader",
    "create_annotation_loader",
    "load_annotation_config",
    "read_ground_truth_jsonl",
    "write_ground_truth_jsonl",
]
