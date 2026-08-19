"""Temporal ROI hold state."""

from __future__ import annotations

from dataclasses import dataclass

from common import ROI


@dataclass
class HeldROI:
    roi: ROI
    remaining_frames: int


class TemporalHold:
    def __init__(self, hold_frames: int) -> None:
        self.hold_frames = hold_frames
        self._held: list[HeldROI] = []

    def update(self, current_rois: list[ROI]) -> list[ROI]:
        if current_rois:
            self._held = [HeldROI(roi, self.hold_frames) for roi in current_rois]
            return [item.roi for item in self._held]

        self._held = [HeldROI(item.roi, item.remaining_frames - 1) for item in self._held if item.remaining_frames > 1]
        return [item.roi for item in self._held]

    def clear(self) -> None:
        self._held = []
