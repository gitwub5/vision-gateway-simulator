"""Event-like map generation for current and future SNN stages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventMaps:
    on_event: object
    off_event: object
    motion_map: object


def encode_event_maps(current_gray, previous_gray, threshold_on: int, threshold_off: int, threshold_motion: int) -> EventMaps:
    import cv2
    import numpy as np

    delta = current_gray.astype(np.int16) - previous_gray.astype(np.int16)
    on_event = (delta > threshold_on).astype("uint8") * 255
    off_event = (delta < -threshold_off).astype("uint8") * 255
    motion_map = (cv2.absdiff(current_gray, previous_gray) > threshold_motion).astype("uint8") * 255
    return EventMaps(on_event=on_event, off_event=off_event, motion_map=motion_map)
