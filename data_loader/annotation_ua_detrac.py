"""UA-DETRAC annotation loading."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from common import GroundTruthAnnotation
from data_loader.annotation_common import AnnotationLoader, dataset_frame_metadata_by_one_based_index
from data_loader.dataset_stream import DatasetConfig


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
        frame_metadata = dataset_frame_metadata_by_one_based_index(self.dataset_config)

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
                vehicle_type = ua_detrac_vehicle_type(target)
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


def ua_detrac_vehicle_type(target: ET.Element) -> str:
    attribute = target.find("attribute")
    if attribute is None:
        return "others"
    return str(attribute.attrib.get("vehicle_type", "others")).strip().lower()
