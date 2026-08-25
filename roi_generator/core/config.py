"""ROI generator configuration parsing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common import FrameSize
from common.io import load_yaml_config


@dataclass(frozen=True)
class RoiGeneratorConfig:
    roi_policy: str = "component_bbox"
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
    budget_enabled: bool = True
    max_roi_per_frame: int = 5
    max_total_roi_area_ratio: float = 0.5
    max_selected_tile_count: int | None = None
    max_tensor_batch_cost: int | None = None
    tile_grid_rows: int = 8
    tile_grid_cols: int = 8
    tile_motion_density_threshold: float = 0.0
    component_filter_enabled: bool = False
    component_filter_min_area_ratio: float | None = None
    component_filter_max_aspect_ratio: float | None = None
    component_filter_min_fill_density: float | None = None
    min_final_roi_width: int = 0
    min_final_roi_height: int = 0
    debug_enabled: bool = False
    debug_max_frames: int | None = None
    debug_stride: int = 1

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
        tile_metadata = roi_generator.get("tile_metadata", {}) or {}
        budget = roi_generator.get("budget", {}) or {}
        component_filter = roi_generator.get("component_filter", {}) or {}
        recall_padding = roi_generator.get("recall_padding", {}) or {}
        debug = roi_generator.get("debug", {}) or {}
        return cls(
            roi_policy=str(roi_generator.get("roi_policy", cls.roi_policy)),
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
            budget_enabled=bool(roi_generator.get("budget_enabled", budget.get("enabled", cls.budget_enabled))),
            max_roi_per_frame=int(
                roi_generator.get("max_roi_per_frame", budget.get("max_roi_per_frame", cls.max_roi_per_frame))
            ),
            max_total_roi_area_ratio=float(
                roi_generator.get(
                    "max_total_roi_area_ratio",
                    budget.get("max_total_roi_area_ratio", cls.max_total_roi_area_ratio),
                )
            ),
            max_selected_tile_count=_optional_int(
                roi_generator.get("max_selected_tile_count", budget.get("max_selected_tile_count"))
            ),
            max_tensor_batch_cost=_optional_int(
                roi_generator.get("max_tensor_batch_cost", budget.get("max_tensor_batch_cost"))
            ),
            tile_grid_rows=max(1, int(roi_generator.get("tile_grid_rows", tile_metadata.get("grid_rows", cls.tile_grid_rows)))),
            tile_grid_cols=max(1, int(roi_generator.get("tile_grid_cols", tile_metadata.get("grid_cols", cls.tile_grid_cols)))),
            tile_motion_density_threshold=float(
                roi_generator.get(
                    "tile_motion_density_threshold",
                    tile_metadata.get("motion_density_threshold", cls.tile_motion_density_threshold),
                )
            ),
            component_filter_enabled=bool(component_filter.get("enabled", cls.component_filter_enabled)),
            component_filter_min_area_ratio=_optional_float(component_filter.get("min_area_ratio")),
            component_filter_max_aspect_ratio=_optional_float(component_filter.get("max_aspect_ratio")),
            component_filter_min_fill_density=_optional_float(component_filter.get("min_fill_density")),
            min_final_roi_width=max(
                0,
                int(
                    roi_generator.get(
                        "min_final_roi_width",
                        recall_padding.get("min_final_roi_width", cls.min_final_roi_width),
                    )
                ),
            ),
            min_final_roi_height=max(
                0,
                int(
                    roi_generator.get(
                        "min_final_roi_height",
                        recall_padding.get("min_final_roi_height", cls.min_final_roi_height),
                    )
                ),
            ),
            debug_enabled=bool(debug.get("enabled", cls.debug_enabled)),
            debug_max_frames=_optional_int(debug.get("max_frames")),
            debug_stride=max(1, int(debug.get("stride", cls.debug_stride))),
        )


def load_roi_generator_config(config_path: str | Path) -> RoiGeneratorConfig:
    config = load_yaml_config(config_path)
    return RoiGeneratorConfig.from_mapping(config)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
