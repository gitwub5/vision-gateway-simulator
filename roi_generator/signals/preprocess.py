"""Preprocessing helpers for low-resolution analysis frames."""

from __future__ import annotations

from common import FrameSize


def to_gray(frame):
    import cv2

    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def resize_for_analysis(gray_frame, analysis_size: FrameSize):
    import cv2

    return cv2.resize(gray_frame, (analysis_size.width, analysis_size.height))
