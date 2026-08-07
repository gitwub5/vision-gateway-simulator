"""Record grouping and formatting helpers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any


FrameKey = tuple[str, int]


def frame_key(camera_id: str, frame_id: int) -> FrameKey:
    return camera_id, frame_id


def group_by_frame(records: Iterable[Any]) -> dict[FrameKey, list[Any]]:
    grouped: dict[FrameKey, list[Any]] = defaultdict(list)
    for record in records:
        grouped[frame_key(record.camera_id, record.frame_id)].append(record)
    return dict(grouped)


def format_ratio(value: float) -> str:
    return f"{value:.3f} ({value * 100:.1f}%)"
