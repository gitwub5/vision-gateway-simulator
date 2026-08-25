"""ROI candidate generation primitives."""

from roi_generator.candidates.components import (
    add_margin_and_clip,
    component_traces_from_rois,
    count_connected_components,
    generate_roi_candidates,
    merge_rois,
    motion_density,
    scale_roi_to_original,
)
from roi_generator.candidates.tiles import scale_tile_traces_to_original, selected_tile_count, tile_traces_from_motion_map

__all__ = [
    "add_margin_and_clip",
    "component_traces_from_rois",
    "count_connected_components",
    "generate_roi_candidates",
    "merge_rois",
    "motion_density",
    "scale_roi_to_original",
    "scale_tile_traces_to_original",
    "selected_tile_count",
    "tile_traces_from_motion_map",
]
