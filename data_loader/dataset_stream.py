"""Frame stream loaders for videos and image sequences."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
import re
from time import time
from typing import Any

from common import FramePacket, FrameSize


DEFAULT_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")


@dataclass(frozen=True)
class DatasetConfig:
    type: str
    input_path: Path
    camera_id: str = "cam_01"
    fps_override: float | None = None
    frame_limit: int | None = None
    start_frame: int = 0
    image_extensions: tuple[str, ...] = DEFAULT_IMAGE_EXTENSIONS

    @classmethod
    def from_mapping(cls, config: dict[str, Any]) -> "DatasetConfig":
        dataset = config.get("dataset", config)
        dataset_type = str(dataset.get("type", "video")).lower()
        input_path = dataset.get("input_path")
        if not input_path:
            raise ValueError("dataset.input_path is required")

        extensions = dataset.get("image_extensions", DEFAULT_IMAGE_EXTENSIONS)
        return cls(
            type=dataset_type,
            input_path=Path(input_path),
            camera_id=str(dataset.get("camera_id", "cam_01")),
            fps_override=dataset.get("fps_override"),
            frame_limit=dataset.get("frame_limit"),
            start_frame=int(dataset.get("start_frame", 0) or 0),
            image_extensions=tuple(str(ext).lower() for ext in extensions),
        )


class DatasetStream:
    """Iterates dataset input as camera-like frame packets."""

    def __iter__(self) -> Iterator[FramePacket]:
        raise NotImplementedError


class VideoFrameStream(DatasetStream):
    def __init__(
        self,
        input_path: str | Path,
        camera_id: str = "cam_01",
        fps_override: float | None = None,
        frame_limit: int | None = None,
        start_frame: int = 0,
    ) -> None:
        self.input_path = Path(input_path)
        self.camera_id = camera_id
        self.fps_override = fps_override
        self.frame_limit = frame_limit
        self.start_frame = start_frame

    def __iter__(self) -> Iterator[FramePacket]:
        cv2 = _require_cv2()

        capture = cv2.VideoCapture(str(self.input_path))
        if not capture.isOpened():
            raise FileNotFoundError(f"Could not open video: {self.input_path}")

        fps = self.fps_override or capture.get(cv2.CAP_PROP_FPS) or 30.0
        capture.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)

        emitted = 0
        frame_id = self.start_frame
        try:
            while self.frame_limit is None or emitted < self.frame_limit:
                ok, frame = capture.read()
                if not ok:
                    break

                height, width = frame.shape[:2]
                timestamp = frame_id / fps
                yield FramePacket(
                    camera_id=self.camera_id,
                    frame_id=frame_id,
                    timestamp=timestamp,
                    frame=frame,
                    original_size=FrameSize(width=width, height=height),
                )
                emitted += 1
                frame_id += 1
        finally:
            capture.release()


class ImageSequenceStream(DatasetStream):
    def __init__(
        self,
        input_path: str | Path,
        camera_id: str = "cam_01",
        fps: float = 30.0,
        extensions: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".bmp"),
        frame_limit: int | None = None,
        start_frame: int = 0,
    ) -> None:
        self.input_path = Path(input_path)
        self.camera_id = camera_id
        self.fps = fps
        self.extensions = tuple(ext.lower() for ext in extensions)
        self.frame_limit = frame_limit
        self.start_frame = start_frame

    def __iter__(self) -> Iterator[FramePacket]:
        cv2 = _require_cv2()

        if not self.input_path.exists():
            raise FileNotFoundError(f"Image sequence directory does not exist: {self.input_path}")
        if not self.input_path.is_dir():
            raise NotADirectoryError(f"Image sequence input is not a directory: {self.input_path}")

        image_paths = list_image_sequence_paths(self.input_path, self.extensions)
        image_paths = image_paths[self.start_frame :]
        if self.frame_limit is not None:
            image_paths = image_paths[: self.frame_limit]

        for offset, image_path in enumerate(image_paths):
            frame_id = self.start_frame + offset
            frame = cv2.imread(str(image_path))
            if frame is None:
                continue

            height, width = frame.shape[:2]
            yield FramePacket(
                camera_id=self.camera_id,
                frame_id=frame_id,
                timestamp=frame_id / self.fps if self.fps else time(),
                frame=frame,
                original_size=FrameSize(width=width, height=height),
            )


def create_dataset_stream(config: DatasetConfig | dict[str, Any]) -> DatasetStream:
    dataset_config = config if isinstance(config, DatasetConfig) else DatasetConfig.from_mapping(config)

    if dataset_config.type == "video":
        return VideoFrameStream(
            input_path=dataset_config.input_path,
            camera_id=dataset_config.camera_id,
            fps_override=dataset_config.fps_override,
            frame_limit=dataset_config.frame_limit,
            start_frame=dataset_config.start_frame,
        )
    if dataset_config.type in {"image_sequence", "images"}:
        fps = dataset_config.fps_override or 30.0
        return ImageSequenceStream(
            input_path=dataset_config.input_path,
            camera_id=dataset_config.camera_id,
            fps=fps,
            extensions=dataset_config.image_extensions,
            frame_limit=dataset_config.frame_limit,
            start_frame=dataset_config.start_frame,
        )

    raise ValueError(f"Unsupported dataset.type: {dataset_config.type}")


def list_image_sequence_paths(
    input_path: str | Path,
    extensions: tuple[str, ...] = DEFAULT_IMAGE_EXTENSIONS,
) -> list[Path]:
    root = Path(input_path)
    normalized_extensions = tuple(ext.lower() for ext in extensions)
    return sorted(
        (path for path in root.iterdir() if path.suffix.lower() in normalized_extensions),
        key=_natural_path_sort_key,
    )


def load_dataset_config(config_path: str | Path) -> DatasetConfig:
    yaml = _require_yaml()
    with Path(config_path).open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    return DatasetConfig.from_mapping(config)


def _require_cv2():
    try:
        import cv2
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "OpenCV is required for dataset loading. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return cv2


def _require_yaml():
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyYAML is required for loading YAML config files. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return yaml


def _natural_path_sort_key(path: Path) -> tuple:
    parts = re.split(r"(\d+)", path.stem)
    stem_key = tuple(int(part) if part.isdigit() else part.lower() for part in parts)
    return stem_key, path.suffix.lower(), path.name.lower()
