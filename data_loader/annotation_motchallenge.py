"""MOTChallenge detection/tracking annotation loading."""

from __future__ import annotations

import csv
from pathlib import Path

from common import GroundTruthAnnotation
from data_loader.annotation_common import AnnotationLoader, dataset_frame_metadata_by_one_based_index
from data_loader.dataset_stream import DatasetConfig


class MotChallengeAnnotationLoader(AnnotationLoader):
    """Loads MOTChallenge gt.txt rows into dataset frame ids.

    MOT rows are comma separated:
    frame, id, left, top, width, height, conf, class, visibility.
    """

    CLASS_MAP = {
        1: (0, "person"),
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
        with annotation_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.reader(handle):
                if len(row) < 6:
                    continue
                source_frame_id = int(float(row[0]))
                if source_frame_id not in frame_metadata:
                    continue
                confidence = float(row[6]) if len(row) > 6 and row[6] else 1.0
                if confidence <= 0:
                    continue
                class_id_raw = int(float(row[7])) if len(row) > 7 and row[7] else 1
                class_id, class_name = self.CLASS_MAP.get(class_id_raw, (class_id_raw, f"class_{class_id_raw}"))
                frame_id, file_name = frame_metadata[source_frame_id]
                left = float(row[2])
                top = float(row[3])
                width = float(row[4])
                height = float(row[5])
                track_id = int(float(row[1])) if row[1] else -1
                annotations.append(
                    GroundTruthAnnotation(
                        camera_id=self.dataset_config.camera_id,
                        frame_id=frame_id,
                        class_id=class_id,
                        class_name=class_name,
                        bbox_xyxy=[left, top, left + width, top + height],
                        annotation_id=f"{self.dataset_config.camera_id}_f{source_frame_id:06d}_track_{track_id}",
                        image_id=source_frame_id,
                        file_name=file_name,
                    )
                )
        return annotations

    def _resolve_annotation_path(self) -> Path:
        if self.input_path is None:
            raise FileNotFoundError("MOTChallenge annotation path is not configured")
        if self.input_path.is_file():
            return self.input_path
        candidate = self.input_path / "gt.txt"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"MOTChallenge gt.txt does not exist: {self.input_path}")
