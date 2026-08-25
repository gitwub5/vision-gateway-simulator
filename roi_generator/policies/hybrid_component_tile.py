"""Component bbox policy filtered by fixed-grid tile activity."""

from __future__ import annotations

from common import FrameSize, ROI
from roi_generator.candidates.components import (
    add_margin_and_clip,
    component_traces_from_rois,
    count_connected_components,
    generate_roi_candidates,
    merge_rois,
    motion_density,
    scale_roi_to_original,
)
from roi_generator.candidates.tiles import scale_tile_traces_to_original, tile_traces_from_motion_map
from roi_generator.core.config import RoiGeneratorConfig
from roi_generator.observability.trace import RoiGenerationTrace, TileTrace
from roi_generator.signals.event_encoder import EventMaps
from roi_generator.signals.motion_detector import filter_motion_map


class HybridComponentTilePolicy:
    name = "hybrid_component_tile"

    def __init__(self, config: RoiGeneratorConfig) -> None:
        self.config = config

    def generate(
        self,
        event_maps: EventMaps,
        analysis_size: FrameSize,
        original_size: FrameSize,
    ) -> RoiGenerationTrace:
        raw_component_count = count_connected_components(event_maps.motion_map)
        filtered_motion = filter_motion_map(event_maps.motion_map, self.config.morphology_kernel_size)
        filtered_component_count = count_connected_components(filtered_motion)
        analysis_rois = generate_roi_candidates(filtered_motion, self.config.min_area_ratio)
        component_traces = component_traces_from_rois(analysis_rois, analysis_size)
        tile_traces = tile_traces_from_motion_map(
            filtered_motion,
            frame_size=analysis_size,
            grid_rows=self.config.tile_grid_rows,
            grid_cols=self.config.tile_grid_cols,
            motion_density_threshold=self.config.tile_motion_density_threshold,
        )
        selected_analysis_rois = [
            roi for roi in analysis_rois if _overlaps_selected_tile(roi, tile_traces)
        ]
        merged_analysis_rois = merge_rois(
            selected_analysis_rois,
            distance_ratio=self.config.merge_distance_ratio,
            frame_size=analysis_size,
        )
        final_rois = [
            add_margin_and_clip(
                scale_roi_to_original(roi, analysis_size, original_size),
                original_size,
                self.config.margin_ratio,
            )
            for roi in merged_analysis_rois
        ]
        return RoiGenerationTrace(
            filtered_motion_map=filtered_motion,
            candidate_analysis_rois=analysis_rois,
            merged_analysis_rois=merged_analysis_rois,
            final_rois=sort_rois_by_area(final_rois),
            component_traces=component_traces,
            tile_traces=scale_tile_traces_to_original(tile_traces, analysis_size, original_size),
            raw_component_count=raw_component_count,
            filtered_component_count=filtered_component_count,
            motion_density=motion_density(filtered_motion),
        )


def _overlaps_selected_tile(roi: ROI, tile_traces: list[TileTrace]) -> bool:
    selected_tiles = [tile for tile in tile_traces if tile.selected]
    if not selected_tiles:
        return False
    return any(_overlaps(roi, tile.bbox) for tile in selected_tiles)


def _overlaps(a: ROI, b: ROI) -> bool:
    return not (
        a.x + a.w <= b.x
        or b.x + b.w <= a.x
        or a.y + a.h <= b.y
        or b.y + b.h <= a.y
    )


def sort_rois_by_area(rois: list[ROI]) -> list[ROI]:
    return sorted(rois, key=lambda roi: roi.area(), reverse=True)
