"""Common interface for ROI proposal policies."""

from __future__ import annotations

from typing import Protocol

from common import FrameSize
from roi_generator.signals.event_encoder import EventMaps
from roi_generator.observability.trace import RoiGenerationTrace


class RoiPolicy(Protocol):
    name: str

    def generate(
        self,
        event_maps: EventMaps,
        analysis_size: FrameSize,
        original_size: FrameSize,
    ) -> RoiGenerationTrace:
        raise NotImplementedError
