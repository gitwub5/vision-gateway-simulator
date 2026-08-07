"""Motion map cleanup helpers."""

from __future__ import annotations


def filter_motion_map(motion_map, kernel_size: int = 3):
    import cv2
    import numpy as np

    kernel = np.ones((kernel_size, kernel_size), dtype="uint8")
    opened = cv2.morphologyEx(motion_map, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)
