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
    adaptive_tile_threshold_enabled: bool = False
    adaptive_tile_threshold_ema_alpha: float = 0.1
    adaptive_tile_threshold_multiplier: float = 1.5
    adaptive_tile_threshold_additive_margin: float = 0.0
    adaptive_tile_threshold_max_threshold: float | None = None
    adaptive_tile_threshold_warmup_frames: int = 0
    rare_tile_guard_enabled: bool = False
    rare_tile_guard_min_history_frames: int = 30
    rare_tile_guard_max_activation_rate: float = 0.05
    rare_tile_guard_weak_density_max: float = 0.02
    small_object_boost_enabled: bool = False
    tile_overlap_ratio: float = 0.0
    reference_feedback_enabled: bool = False
    reference_feedback_ttl_frames: int = 30
    reference_feedback_min_confidence: float = 0.25
    reference_feedback_margin_ratio: float = 0.2
    reference_feedback_max_candidates_per_frame: int = 3
    reference_feedback_duplicate_overlap_ratio: float = 1.0
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
        roi_generator = config.get("roi_generator", config)
        processing = roi_generator.get("processing", {}) or {}
        tile_metadata = roi_generator.get("tile_metadata", {}) or {}
        adaptive_tile_threshold = roi_generator.get("adaptive_tile_threshold", {}) or {}
        rare_tile_guard = roi_generator.get("rare_tile_guard", {}) or {}
        budget = roi_generator.get("budget", {}) or {}
        small_object_boost = roi_generator.get("small_object_boost", {}) or {}
        reference_feedback = roi_generator.get("reference_feedback", {}) or {}
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
            adaptive_tile_threshold_enabled=bool(
                roi_generator.get(
                    "adaptive_tile_threshold_enabled",
                    adaptive_tile_threshold.get("enabled", cls.adaptive_tile_threshold_enabled),
                )
            ),
            adaptive_tile_threshold_ema_alpha=_bounded_ratio(
                roi_generator.get(
                    "adaptive_tile_threshold_ema_alpha",
                    adaptive_tile_threshold.get("ema_alpha", cls.adaptive_tile_threshold_ema_alpha),
                )
            ),
            adaptive_tile_threshold_multiplier=max(
                0.0,
                float(
                    roi_generator.get(
                        "adaptive_tile_threshold_multiplier",
                        adaptive_tile_threshold.get("multiplier", cls.adaptive_tile_threshold_multiplier),
                    )
                ),
            ),
            adaptive_tile_threshold_additive_margin=max(
                0.0,
                float(
                    roi_generator.get(
                        "adaptive_tile_threshold_additive_margin",
                        adaptive_tile_threshold.get(
                            "additive_margin",
                            cls.adaptive_tile_threshold_additive_margin,
                        ),
                    )
                ),
            ),
            adaptive_tile_threshold_max_threshold=_optional_float(
                roi_generator.get(
                    "adaptive_tile_threshold_max_threshold",
                    adaptive_tile_threshold.get("max_threshold"),
                )
            ),
            adaptive_tile_threshold_warmup_frames=max(
                0,
                int(
                    roi_generator.get(
                        "adaptive_tile_threshold_warmup_frames",
                        adaptive_tile_threshold.get(
                            "warmup_frames",
                            cls.adaptive_tile_threshold_warmup_frames,
                        ),
                    )
                ),
            ),
            rare_tile_guard_enabled=bool(
                roi_generator.get(
                    "rare_tile_guard_enabled",
                    rare_tile_guard.get("enabled", cls.rare_tile_guard_enabled),
                )
            ),
            rare_tile_guard_min_history_frames=max(
                0,
                int(
                    roi_generator.get(
                        "rare_tile_guard_min_history_frames",
                        rare_tile_guard.get(
                            "min_history_frames",
                            cls.rare_tile_guard_min_history_frames,
                        ),
                    )
                ),
            ),
            rare_tile_guard_max_activation_rate=_bounded_ratio(
                roi_generator.get(
                    "rare_tile_guard_max_activation_rate",
                    rare_tile_guard.get(
                        "max_activation_rate",
                        cls.rare_tile_guard_max_activation_rate,
                    ),
                )
            ),
            rare_tile_guard_weak_density_max=max(
                0.0,
                float(
                    roi_generator.get(
                        "rare_tile_guard_weak_density_max",
                        rare_tile_guard.get(
                            "weak_density_max",
                            cls.rare_tile_guard_weak_density_max,
                        ),
                    )
                ),
            ),
            small_object_boost_enabled=bool(
                roi_generator.get(
                    "small_object_boost_enabled",
                    small_object_boost.get("enabled", cls.small_object_boost_enabled),
                )
            ),
            tile_overlap_ratio=_ratio(
                roi_generator.get(
                    "tile_overlap_ratio",
                    small_object_boost.get("tile_overlap_ratio", cls.tile_overlap_ratio),
                )
            ),
            reference_feedback_enabled=bool(
                roi_generator.get(
                    "reference_feedback_enabled",
                    reference_feedback.get("enabled", cls.reference_feedback_enabled),
                )
            ),
            reference_feedback_ttl_frames=max(
                0,
                int(
                    roi_generator.get(
                        "reference_feedback_ttl_frames",
                        reference_feedback.get("ttl_frames", cls.reference_feedback_ttl_frames),
                    )
                ),
            ),
            reference_feedback_min_confidence=float(
                roi_generator.get(
                    "reference_feedback_min_confidence",
                    reference_feedback.get("min_confidence", cls.reference_feedback_min_confidence),
                )
            ),
            reference_feedback_margin_ratio=_ratio(
                roi_generator.get(
                    "reference_feedback_margin_ratio",
                    reference_feedback.get("margin_ratio", cls.reference_feedback_margin_ratio),
                )
            ),
            reference_feedback_max_candidates_per_frame=max(
                0,
                int(
                    roi_generator.get(
                        "reference_feedback_max_candidates_per_frame",
                        reference_feedback.get(
                            "max_candidates_per_frame",
                            cls.reference_feedback_max_candidates_per_frame,
                        ),
                    )
                ),
            ),
            reference_feedback_duplicate_overlap_ratio=_bounded_ratio(
                roi_generator.get(
                    "reference_feedback_duplicate_overlap_ratio",
                    reference_feedback.get(
                        "duplicate_overlap_ratio",
                        cls.reference_feedback_duplicate_overlap_ratio,
                    ),
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


def _ratio(value: Any) -> float:
    return max(0.0, float(value))


def _bounded_ratio(value: Any) -> float:
    return min(1.0, max(0.0, float(value)))
