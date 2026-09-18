"""Mall Dataset head-point annotation loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import GroundTruthAnnotation
from data_loader.annotation_common import AnnotationLoader, dataset_frame_metadata_by_one_based_index
from data_loader.dataset_stream import DatasetConfig


class MallDatasetAnnotationLoader(AnnotationLoader):
    """Loads Mall Dataset head points as small bbox proxies for ROI containment."""

    def __init__(
        self,
        input_path: str | Path,
        dataset_config: DatasetConfig,
        annotation_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(input_path)
        self.dataset_config = dataset_config
        self.annotation_config = annotation_config or {}
        self.proxy_width = float(self.annotation_config.get("proxy_box_width", 24))
        self.proxy_height = float(self.annotation_config.get("proxy_box_height", 48))

    def load(self) -> list[GroundTruthAnnotation]:
        if self.input_path is None:
            return []
        if not self.input_path.exists():
            raise FileNotFoundError(f"Mall Dataset annotation file does not exist: {self.input_path}")

        scipy_io = _require_scipy_io()
        data = scipy_io.loadmat(self.input_path)
        frames = data["frame"]
        frame_metadata = dataset_frame_metadata_by_one_based_index(self.dataset_config)

        annotations: list[GroundTruthAnnotation] = []
        half_width = self.proxy_width / 2.0
        height_above_head = self.proxy_height * 0.2
        height_below_head = self.proxy_height * 0.8
        for source_frame_id, (frame_id, file_name) in frame_metadata.items():
            if source_frame_id < 1 or source_frame_id > frames.shape[1]:
                continue
            locations = frames[0, source_frame_id - 1]["loc"][0, 0]
            for point_index, point in enumerate(locations):
                x = float(point[0])
                y = float(point[1])
                annotations.append(
                    GroundTruthAnnotation(
                        camera_id=self.dataset_config.camera_id,
                        frame_id=frame_id,
                        class_id=0,
                        class_name="person",
                        bbox_xyxy=[
                            max(0.0, x - half_width),
                            max(0.0, y - height_above_head),
                            x + half_width,
                            y + height_below_head,
                        ],
                        annotation_id=f"mall_f{source_frame_id:06d}_head_{point_index}",
                        image_id=source_frame_id,
                        file_name=file_name,
                        source="mall_head_point_proxy_box",
                    )
                )
        return annotations


def _require_scipy_io():
    try:
        import scipy.io
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "scipy is required for Mall Dataset .mat annotation loading. "
            "Install project dependencies with `pip install -r requirements.txt`."
        ) from exc
    return scipy.io
