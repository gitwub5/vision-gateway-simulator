"""Fixed-grid tile mask ROI policy."""

from __future__ import annotations

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

    def generate(
        self,
        event_maps: EventMaps,
        analysis_size: FrameSize,
        original_size: FrameSize,
    ) -> RoiGenerationTrace:
        filtered_motion = filter_motion_map(event_maps.motion_map, self.config.morphology_kernel_size)
        tile_traces = tile_traces_from_motion_map(
            filtered_motion,
            frame_size=analysis_size,
            grid_rows=self.config.tile_grid_rows,
            grid_cols=self.config.tile_grid_cols,
            motion_density_threshold=self.config.tile_motion_density_threshold,
        )
        selected_analysis_rois = selected_tile_rois(tile_traces)
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


def sort_rois_by_area(rois: list[ROI]) -> list[ROI]:
    return sorted(rois, key=lambda roi: roi.area(), reverse=True)
