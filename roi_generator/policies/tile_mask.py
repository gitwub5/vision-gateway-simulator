"""Fixed-grid tile mask ROI policy."""

from __future__ import annotations

from dataclasses import replace

from common import FrameSize, ROI
from roi_generator.candidates.components import merge_rois, motion_density, scale_roi_to_original
from roi_generator.candidates.tiles import (
    scale_tile_traces_to_original,
    selected_tile_rois,
    tile_traces_from_motion_map,
)
from roi_generator.core.config import RoiGeneratorConfig
from roi_generator.observability.trace import RoiGenerationTrace
from roi_generator.signals.event_encoder import EventMaps
from roi_generator.signals.motion_detector import filter_motion_map


class TileMaskPolicy:
    name = "tile_mask"

    def __init__(self, config: RoiGeneratorConfig) -> None:
        self.config = config
        self._tile_density_ema: dict[tuple[int, int], float] = {}
        self._tile_seen_count: dict[tuple[int, int], int] = {}
        self._tile_selected_count: dict[tuple[int, int], int] = {}
        self._frames_processed = 0

    def generate(
        self,
        event_maps: EventMaps,
        analysis_size: FrameSize,
        original_size: FrameSize,
    ) -> RoiGenerationTrace:
        filtered_motion = filter_motion_map(event_maps.motion_map, self.config.morphology_kernel_size)
        tile_thresholds = self._adaptive_thresholds() if self.config.adaptive_tile_threshold_enabled else None
        tile_traces = tile_traces_from_motion_map(
            filtered_motion,
            frame_size=analysis_size,
            grid_rows=self.config.tile_grid_rows,
            grid_cols=self.config.tile_grid_cols,
            motion_density_threshold=self.config.tile_motion_density_threshold,
            tile_thresholds=tile_thresholds,
        )
        if self.config.adaptive_tile_threshold_enabled:
            tile_traces = [
                replace(
                    tile,
                    selection_reason=adaptive_selection_reason(
                        tile.motion_density,
                        tile.motion_threshold,
                        self.config.tile_motion_density_threshold,
                    ),
                )
                for tile in tile_traces
            ]
        if self.config.neighbor_rescue_enabled:
            tile_traces = self._apply_neighbor_rescue(tile_traces)
        if self.config.rare_tile_guard_enabled:
            tile_traces = self._apply_rare_tile_guard(tile_traces)
        if (
            self.config.adaptive_tile_threshold_enabled
            or self.config.rare_tile_guard_enabled
            or self.config.neighbor_rescue_enabled
        ):
            self._update_tile_history(tile_traces)
        tile_overlap_ratio = self.config.tile_overlap_ratio if self.config.small_object_boost_enabled else 0.0
        selected_analysis_rois = selected_tile_rois(
            tile_traces,
            overlap_ratio=tile_overlap_ratio,
            frame_size=analysis_size,
        )
        merged_analysis_rois = merge_rois(
            selected_analysis_rois,
            distance_ratio=0.0,
            frame_size=analysis_size,
        )
        final_rois = [
            scale_roi_to_original(roi, analysis_size, original_size)
            for roi in merged_analysis_rois
        ]
        return RoiGenerationTrace(
            filtered_motion_map=filtered_motion,
            candidate_analysis_rois=selected_analysis_rois,
            merged_analysis_rois=merged_analysis_rois,
            final_rois=sort_rois_by_area(final_rois),
            tile_traces=scale_tile_traces_to_original(tile_traces, analysis_size, original_size),
            motion_density=motion_density(filtered_motion),
        )

    def _adaptive_thresholds(self) -> dict[tuple[int, int], float]:
        if self._frames_processed < self.config.adaptive_tile_threshold_warmup_frames:
            return {}
        thresholds: dict[tuple[int, int], float] = {}
        for row in range(self.config.tile_grid_rows):
            for col in range(self.config.tile_grid_cols):
                base_threshold = self.config.tile_motion_density_threshold
                history_threshold = (
                    self._tile_density_ema.get((row, col), 0.0)
                    * self.config.adaptive_tile_threshold_multiplier
                    + self.config.adaptive_tile_threshold_additive_margin
                )
                threshold = max(base_threshold, history_threshold)
                if self.config.adaptive_tile_threshold_max_threshold is not None:
                    threshold = min(threshold, self.config.adaptive_tile_threshold_max_threshold)
                thresholds[(row, col)] = threshold
        return thresholds

    def _apply_rare_tile_guard(self, tile_traces):
        guarded = []
        for tile in tile_traces:
            key = (tile.row, tile.col)
            seen_count = self._tile_seen_count.get(key, 0)
            selected_count = self._tile_selected_count.get(key, 0)
            activation_rate = selected_count / seen_count if seen_count else 0.0
            should_suppress = (
                tile.selected
                and seen_count >= self.config.rare_tile_guard_min_history_frames
                and activation_rate <= self.config.rare_tile_guard_max_activation_rate
                and tile.motion_density <= self.config.rare_tile_guard_weak_density_max
            )
            guarded.append(
                replace(tile, selected=False, selection_reason="rare_tile_guard_suppressed")
                if should_suppress
                else tile
            )
        return guarded

    def _apply_neighbor_rescue(self, tile_traces):
        selected_keys = {(tile.row, tile.col) for tile in tile_traces if tile.selected}
        if not selected_keys:
            return tile_traces

        rescue_density = self.config.neighbor_rescue_min_density
        if rescue_density is None:
            rescue_density = (
                self.config.tile_motion_density_threshold
                * self.config.neighbor_rescue_min_density_ratio
            )

        rescue_candidates = []
        for index, tile in enumerate(tile_traces):
            if tile.selected or tile.motion_density < rescue_density:
                continue
            if not _is_neighbor_of_selected(tile.row, tile.col, selected_keys):
                continue
            rescue_candidates.append((index, tile.motion_density))

        rescue_candidates.sort(key=lambda item: item[1], reverse=True)
        if self.config.neighbor_rescue_max_added_tiles is not None:
            rescue_candidates = rescue_candidates[: max(0, self.config.neighbor_rescue_max_added_tiles)]
        rescue_indices = {index for index, _density in rescue_candidates}

        return [
            replace(tile, selected=True, selection_reason="neighbor_motion_weak")
            if index in rescue_indices
            else tile
            for index, tile in enumerate(tile_traces)
        ]

    def _update_tile_history(self, tile_traces) -> None:
        alpha = self.config.adaptive_tile_threshold_ema_alpha
        for tile in tile_traces:
            key = (tile.row, tile.col)
            previous = self._tile_density_ema.get(key, tile.motion_density)
            self._tile_density_ema[key] = (alpha * tile.motion_density) + ((1.0 - alpha) * previous)
            self._tile_seen_count[key] = self._tile_seen_count.get(key, 0) + 1
            if tile.selected:
                self._tile_selected_count[key] = self._tile_selected_count.get(key, 0) + 1
        self._frames_processed += 1


def sort_rois_by_area(rois: list[ROI]) -> list[ROI]:
    return sorted(rois, key=lambda roi: roi.area(), reverse=True)


def adaptive_selection_reason(density: float, threshold: float, base_threshold: float) -> str:
    if density <= threshold:
        return "below_adaptive_threshold" if threshold > base_threshold else "below_motion_threshold"
    return "adaptive_motion_threshold" if threshold > base_threshold else "motion_threshold"


def _is_neighbor_of_selected(row: int, col: int, selected_keys: set[tuple[int, int]]) -> bool:
    for selected_row, selected_col in selected_keys:
        if selected_row == row and selected_col == col:
            continue
        if abs(selected_row - row) <= 1 and abs(selected_col - col) <= 1:
            return True
    return False
