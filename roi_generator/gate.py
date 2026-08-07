"""Rule-based ROI generator orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

from common import FramePacket, FrameSize, ROI, TriggerType
from roi_generator.event_encoder import EventMaps, encode_event_maps
from roi_generator.motion_detector import filter_motion_map
from roi_generator.preprocess import resize_for_analysis, to_gray
from roi_generator.roi_generator import (
    add_margin_and_clip,
    generate_roi_candidates,
    merge_rois,
    scale_roi_to_original,
)
from roi_generator.temporal_hold import TemporalHold


@dataclass(frozen=True)
class RoiGeneratorConfig:
    analysis_width: int = 256
    analysis_height: int = 144
    processing_width: int | None = None
    processing_height: int | None = None
    processing_allow_upscale: bool = False
    threshold_motion: int = 25
    threshold_on: int = 15
    threshold_off: int = 15
    morphology_kernel_size: int = 3
    min_area_ratio: float = 0.001
    merge_distance_ratio: float = 0.08
    margin_ratio: float = 0.25
    hold_frames: int = 15
    full_frame_interval: int = 60
    max_roi_per_frame: int = 5
    max_total_roi_area_ratio: float = 0.5

    @property
    def analysis_size(self) -> FrameSize:
        return FrameSize(width=self.analysis_width, height=self.analysis_height)

    def analysis_size_for_frame(self, original_size: FrameSize) -> FrameSize:
        if self.processing_width is None and self.processing_height is None:
            return self.analysis_size

        width = self.processing_width
        height = self.processing_height
        if width is None:
            width = round(original_size.width * (height / original_size.height))
        if height is None:
            height = round(original_size.height * (width / original_size.width))

        width = max(1, int(width))
        height = max(1, int(height))
        if not self.processing_allow_upscale:
            scale = min(1.0, original_size.width / width, original_size.height / height)
            width = max(1, round(width * scale))
            height = max(1, round(height * scale))
        return FrameSize(width=width, height=height)

    @classmethod
    def from_mapping(cls, config: dict[str, Any]) -> "RoiGeneratorConfig":
        roi_generator = config.get("roi_generator", config.get("npx_gate", config))
        processing = roi_generator.get("processing", {}) or {}
        return cls(
            analysis_width=int(roi_generator.get("analysis_width", cls.analysis_width)),
            analysis_height=int(roi_generator.get("analysis_height", cls.analysis_height)),
            processing_width=_optional_int(roi_generator.get("processing_width", processing.get("width"))),
            processing_height=_optional_int(roi_generator.get("processing_height", processing.get("height"))),
            processing_allow_upscale=bool(
                roi_generator.get(
                    "processing_allow_upscale",
                    processing.get("allow_upscale", cls.processing_allow_upscale),
                )
            ),
            threshold_motion=int(roi_generator.get("threshold_motion", cls.threshold_motion)),
            threshold_on=int(roi_generator.get("threshold_on", cls.threshold_on)),
            threshold_off=int(roi_generator.get("threshold_off", cls.threshold_off)),
            morphology_kernel_size=int(roi_generator.get("morphology_kernel_size", cls.morphology_kernel_size)),
            min_area_ratio=float(roi_generator.get("min_area_ratio", cls.min_area_ratio)),
            merge_distance_ratio=float(roi_generator.get("merge_distance_ratio", cls.merge_distance_ratio)),
            margin_ratio=float(roi_generator.get("margin_ratio", cls.margin_ratio)),
            hold_frames=int(roi_generator.get("hold_frames", cls.hold_frames)),
            full_frame_interval=int(roi_generator.get("full_frame_interval", cls.full_frame_interval)),
            max_roi_per_frame=int(roi_generator.get("max_roi_per_frame", cls.max_roi_per_frame)),
            max_total_roi_area_ratio=float(
                roi_generator.get("max_total_roi_area_ratio", cls.max_total_roi_area_ratio)
            ),
        )


@dataclass(frozen=True)
class GateDecision:
    camera_id: str
    frame_id: int
    timestamp: float
    trigger_type: TriggerType
    rois: list[ROI]
    original_frame_size: FrameSize
    analysis_frame_size: FrameSize
    gate_latency_ms: float
    should_run_full_frame: bool = False
    event_maps: EventMaps | None = field(default=None, repr=False, compare=False)


class RuleBasedRoiGenerator:
    """Converts FramePacket input into ROI or full-frame trigger decisions."""

    def __init__(self, config: RoiGeneratorConfig) -> None:
        self.config = config
        self._temporal_hold = TemporalHold(config.hold_frames)
        self._previous_analysis_gray = None
        self._previous_analysis_size: FrameSize | None = None

    def process(self, packet: FramePacket) -> GateDecision:
        started = perf_counter()
        analysis_size = self.config.analysis_size_for_frame(packet.original_size)
        analysis_gray = resize_for_analysis(to_gray(packet.frame), analysis_size)

        if self._previous_analysis_gray is None:
            self._previous_analysis_gray = analysis_gray
            self._previous_analysis_size = analysis_size
            return self._decision(
                packet=packet,
                trigger_type=TriggerType.FULL_FRAME,
                rois=[],
                started=started,
                should_run_full_frame=True,
                event_maps=None,
                analysis_size=analysis_size,
            )

        if self._previous_analysis_size != analysis_size:
            self._previous_analysis_gray = analysis_gray
            self._previous_analysis_size = analysis_size
            self._temporal_hold.clear()
            return self._decision(
                packet=packet,
                trigger_type=TriggerType.FULL_FRAME,
                rois=[],
                started=started,
                should_run_full_frame=True,
                event_maps=None,
                analysis_size=analysis_size,
            )

        event_maps = encode_event_maps(
            current_gray=analysis_gray,
            previous_gray=self._previous_analysis_gray,
            threshold_on=self.config.threshold_on,
            threshold_off=self.config.threshold_off,
            threshold_motion=self.config.threshold_motion,
        )
        self._previous_analysis_gray = analysis_gray
        self._previous_analysis_size = analysis_size

        filtered_motion = filter_motion_map(event_maps.motion_map, self.config.morphology_kernel_size)
        analysis_rois = generate_roi_candidates(filtered_motion, self.config.min_area_ratio)
        merged_analysis_rois = merge_rois(
            analysis_rois,
            distance_ratio=self.config.merge_distance_ratio,
            frame_size=analysis_size,
        )
        current_rois = [
            add_margin_and_clip(
                scale_roi_to_original(roi, analysis_size, packet.original_size),
                packet.original_size,
                self.config.margin_ratio,
            )
            for roi in merged_analysis_rois
        ]
        current_rois = sort_rois_by_area(current_rois)

        if should_fallback_to_full_frame(current_rois, packet.original_size, self.config):
            self._temporal_hold.clear()
            return self._decision(
                packet=packet,
                trigger_type=TriggerType.FALLBACK_FULL_FRAME,
                rois=[],
                started=started,
                should_run_full_frame=True,
                event_maps=event_maps,
                analysis_size=analysis_size,
            )

        held_rois = self._temporal_hold.update(current_rois)
        if current_rois:
            trigger_type = TriggerType.ROI
            rois = current_rois
        elif held_rois:
            trigger_type = TriggerType.HOLD
            rois = held_rois
        else:
            trigger_type = TriggerType.NONE
            rois = []

        if is_periodic_full_frame(packet.frame_id, self.config.full_frame_interval):
            return self._decision(
                packet=packet,
                trigger_type=TriggerType.FULL_FRAME,
                rois=rois,
                started=started,
                should_run_full_frame=True,
                event_maps=event_maps,
                analysis_size=analysis_size,
            )

        return self._decision(
            packet=packet,
            trigger_type=trigger_type,
            rois=rois,
            started=started,
            should_run_full_frame=False,
            event_maps=event_maps,
            analysis_size=analysis_size,
        )

    def _decision(
        self,
        packet: FramePacket,
        trigger_type: TriggerType,
        rois: list[ROI],
        started: float,
        should_run_full_frame: bool,
        event_maps: EventMaps | None,
        analysis_size: FrameSize | None = None,
    ) -> GateDecision:
        if analysis_size is None:
            analysis_size = self.config.analysis_size_for_frame(packet.original_size)
        return GateDecision(
            camera_id=packet.camera_id,
            frame_id=packet.frame_id,
            timestamp=packet.timestamp,
            trigger_type=trigger_type,
            rois=rois,
            original_frame_size=packet.original_size,
            analysis_frame_size=analysis_size,
            gate_latency_ms=(perf_counter() - started) * 1000.0,
            should_run_full_frame=should_run_full_frame,
            event_maps=event_maps,
        )


def should_fallback_to_full_frame(rois: list[ROI], frame_size: FrameSize, config: RoiGeneratorConfig) -> bool:
    if not rois:
        return False
    if len(rois) > config.max_roi_per_frame:
        return True

    total_roi_area = sum(roi.area() for roi in rois)
    frame_area = frame_size.area()
    if frame_area <= 0:
        return True
    return total_roi_area / frame_area > config.max_total_roi_area_ratio


def is_periodic_full_frame(frame_id: int, interval: int) -> bool:
    return interval > 0 and frame_id > 0 and frame_id % interval == 0


def sort_rois_by_area(rois: list[ROI]) -> list[ROI]:
    return sorted(rois, key=lambda roi: roi.area(), reverse=True)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def load_roi_generator_config(config_path: str | Path) -> RoiGeneratorConfig:
    yaml = _require_yaml()
    with Path(config_path).open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    return RoiGeneratorConfig.from_mapping(config)


def _require_yaml():
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyYAML is required for loading YAML config files. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return yaml
