"""Low-level frame signal extraction helpers."""

from roi_generator.signals.event_encoder import EventMaps, encode_event_maps
from roi_generator.signals.motion_detector import filter_motion_map
from roi_generator.signals.preprocess import resize_for_analysis, to_gray

__all__ = [
    "EventMaps",
    "encode_event_maps",
    "filter_motion_map",
    "resize_for_analysis",
    "to_gray",
]
