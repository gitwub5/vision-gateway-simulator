"""Backward-compatible signal encoder imports."""

from __future__ import annotations

from roi_generator.signals.event_encoder import EventMaps, encode_event_maps

__all__ = ["EventMaps", "encode_event_maps"]
