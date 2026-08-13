"""ROI candidate generation primitives."""

from roi_generator.candidates.components import (
    add_margin_and_clip,
    generate_roi_candidates,
    merge_rois,
    scale_roi_to_original,
)

__all__ = [
    "add_margin_and_clip",
    "generate_roi_candidates",
    "merge_rois",
    "scale_roi_to_original",
]
