"""Shared OpenCV drawing primitives for ROI visualizations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import GroundTruthAnnotation, ROI


COLOR_ROI = (0, 220, 255)
COLOR_TILE = (180, 120, 40)
COLOR_FEEDBACK = (80, 220, 80)
COLOR_GT_CONTAINED = (255, 0, 255)
COLOR_GT_MISSED = (0, 0, 255)
COLOR_COMPONENT = (0, 180, 255)
COLOR_MERGED = (0, 255, 120)
COLOR_TEXT = (235, 235, 235)
COLOR_PANEL = (28, 28, 28)


def load_visualization_dependencies():
    try:
        import cv2
        import numpy as np
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "OpenCV and NumPy are required for visualization. "
            "Install project dependencies with `pip install -r requirements.txt`."
        ) from exc
    return cv2, np


def clear_images(directory: str | Path, suffixes: tuple[str, ...] = (".jpg", ".png")) -> None:
    root = Path(directory)
    for suffix in suffixes:
        for path in root.glob(f"*{suffix}"):
            if path.is_file():
                path.unlink()


def frame_stem(camera_id: str, frame_id: int) -> str:
    safe_camera_id = camera_id.replace("/", "_").replace(" ", "_")
    return f"{safe_camera_id}_f{frame_id:06d}"


def draw_title(cv2: Any, canvas: Any, title: str) -> None:
    width = min(canvas.shape[1], 520)
    cv2.rectangle(canvas, (0, 0), (width, 28), (32, 32, 32), -1)
    cv2.putText(canvas, title, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_TEXT, 1, cv2.LINE_AA)


def draw_label(
    cv2: Any,
    canvas: Any,
    label: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    cv2.putText(
        canvas,
        label,
        (x, max(16, y) - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        color,
        1,
        cv2.LINE_AA,
    )


def draw_xyxy(
    cv2: Any,
    canvas: Any,
    bbox_xyxy: list[float],
    color: tuple[int, int, int],
    label: str = "",
    scale: float = 1.0,
    thickness: int = 2,
) -> None:
    x1, y1, x2, y2 = [int(round(value * scale)) for value in bbox_xyxy]
    cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)
    if label:
        draw_label(cv2, canvas, label, x1, y1, color)


def draw_roi(
    cv2: Any,
    canvas: Any,
    roi: ROI,
    color: tuple[int, int, int] = COLOR_ROI,
    label: str = "ROI",
) -> None:
    draw_xyxy(cv2, canvas, [roi.x, roi.y, roi.x + roi.w, roi.y + roi.h], color, label)


def draw_roi_record(
    cv2: Any,
    canvas: Any,
    record: dict[str, Any],
    color: tuple[int, int, int] = COLOR_ROI,
    label: str = "ROI",
    scale: float = 1.0,
) -> None:
    x, y, w, h = record["roi_xywh"]
    draw_xyxy(cv2, canvas, [x, y, x + w, y + h], color, label, scale)


def draw_gt(
    cv2: Any,
    canvas: Any,
    gt: GroundTruthAnnotation,
    contained: bool | None = None,
    label_prefix: str = "GT",
) -> None:
    color = COLOR_GT_CONTAINED if contained is not False else COLOR_GT_MISSED
    draw_xyxy(cv2, canvas, gt.bbox_xyxy, color, f"{label_prefix}:{gt.class_name}")


def draw_gt_record(
    cv2: Any,
    canvas: Any,
    record: dict[str, Any],
    contained: bool,
    scale: float = 1.0,
) -> None:
    color = COLOR_GT_CONTAINED if contained else COLOR_GT_MISSED
    draw_xyxy(
        cv2,
        canvas,
        record["bbox_xyxy"],
        color,
        "GT hit" if contained else "GT miss",
        scale,
    )


def draw_filled_xyxy(
    cv2: Any,
    canvas: Any,
    bbox_xyxy: list[float],
    color: tuple[int, int, int],
    alpha: float,
    scale: float = 1.0,
) -> None:
    x1, y1, x2, y2 = [int(round(value * scale)) for value in bbox_xyxy]
    overlay = canvas.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    cv2.addWeighted(overlay, alpha, canvas, 1 - alpha, 0, canvas)


def blank_panel(cv2: Any, frame: Any, title: str) -> Any:
    panel = frame.copy()
    height, width = frame.shape[:2]
    cv2.rectangle(panel, (0, 0), (width, height), COLOR_PANEL, -1)
    draw_title(cv2, panel, title)
    return panel
