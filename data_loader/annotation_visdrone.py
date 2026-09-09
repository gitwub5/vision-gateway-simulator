"""VisDrone-VID annotation loading."""

from __future__ import annotations

from pathlib import Path

from common import GroundTruthAnnotation
from data_loader.annotation_common import AnnotationLoader, dataset_frame_metadata_by_one_based_index
from data_loader.dataset_stream import DatasetConfig


class VisDroneVidAnnotationLoader(AnnotationLoader):
    """Loads VisDrone video detection annotations into dataset frame ids."""

    CLASS_MAP = {
        1: "pedestrian",
        2: "people",
        3: "bicycle",
        4: "car",
        5: "van",
        6: "truck",
        7: "tricycle",
        8: "awning-tricycle",
        9: "bus",
        10: "motor",
    }

    def __init__(self, input_path: str | Path, dataset_config: DatasetConfig) -> None:
        super().__init__(input_path)
        self.dataset_config = dataset_config

    def load(self) -> list[GroundTruthAnnotation]:
        if self.input_path is None:
            return []
        annotation_path = self._resolve_annotation_path()
        frame_metadata = dataset_frame_metadata_by_one_based_index(self.dataset_config)

        annotations: list[GroundTruthAnnotation] = []
        with annotation_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                values = [value.strip() for value in line.split(",")]
                if len(values) < 8:
                    continue
                source_frame_id = int(values[0])
                if source_frame_id not in frame_metadata:
                    continue
                score = float(values[6])
                category_id = int(values[7])
                if score <= 0 or category_id not in self.CLASS_MAP:
                    continue

                x = float(values[2])
                y = float(values[3])
                width = float(values[4])
                height = float(values[5])
                frame_id, file_name = frame_metadata[source_frame_id]
                target_id = values[1]
                annotations.append(
                    GroundTruthAnnotation(
                        camera_id=self.dataset_config.camera_id,
                        frame_id=frame_id,
                        class_id=category_id,
                        class_name=self.CLASS_MAP[category_id],
                        bbox_xyxy=[x, y, x + width, y + height],
                        annotation_id=(
                            f"{self.dataset_config.camera_id}_f{source_frame_id:07d}_"
                            f"target_{target_id}_line_{line_number}"
                        ),
                        image_id=source_frame_id,
                        file_name=file_name,
                    )
                )
        return annotations

    def _resolve_annotation_path(self) -> Path:
        if self.input_path is None:
            raise FileNotFoundError("VisDrone annotation path is not configured")
        if self.input_path.is_file():
            return self.input_path
        if self.input_path.is_dir():
            candidate = self.input_path / f"{self.dataset_config.camera_id}.txt"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"VisDrone annotation TXT does not exist: {self.input_path}")
