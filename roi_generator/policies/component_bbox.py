"""Connected-component bbox ROI policy."""

from __future__ import annotations

from common import FrameSize, ROI
from roi_generator.core.config import RoiGeneratorConfig
from roi_generator.signals.event_encoder import EventMaps
from roi_generator.signals.motion_detector import filter_motion_map
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
from roi_generator.observability.trace import RoiGenerationTrace


class ComponentBboxPolicy:
    name = "component_bbox"

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
        filtered_analysis_rois = self._filter_component_rois(analysis_rois, component_traces)
        tile_traces = scale_tile_traces_to_original(
            tile_traces_from_motion_map(
                filtered_motion,
                frame_size=analysis_size,
                grid_rows=self.config.tile_grid_rows,
                grid_cols=self.config.tile_grid_cols,
                motion_density_threshold=self.config.tile_motion_density_threshold,
            ),
            analysis_size=analysis_size,
            original_size=original_size,
        )
        merged_analysis_rois = merge_rois(
            filtered_analysis_rois,
            distance_ratio=self.config.merge_distance_ratio,
            frame_size=analysis_size,
        )
        current_rois = [
            add_margin_and_clip(
                scale_roi_to_original(roi, analysis_size, original_size),
                original_size,
                self.config.margin_ratio,
            )
            for roi in merged_analysis_rois
        ]
        current_rois = [self._expand_to_min_size(roi, original_size) for roi in current_rois]
        return RoiGenerationTrace(
            filtered_motion_map=filtered_motion,
            candidate_analysis_rois=analysis_rois,
            merged_analysis_rois=merged_analysis_rois,
            final_rois=sort_rois_by_area(current_rois),
            component_traces=component_traces,
            tile_traces=tile_traces,
            raw_component_count=raw_component_count,
            filtered_component_count=filtered_component_count,
            motion_density=motion_density(filtered_motion),
        )

    def _filter_component_rois(self, rois, traces):
        if not self.config.component_filter_enabled:
            return rois
        trace_by_id = {trace.component_id: trace for trace in traces}
        filtered = []
        for index, roi in enumerate(rois, start=1):
            trace = trace_by_id.get(index)
            if trace is None:
                continue
            if self.config.component_filter_min_area_ratio is not None:
                if trace.component_area_ratio < self.config.component_filter_min_area_ratio:
                    continue
            if self.config.component_filter_max_aspect_ratio is not None:
                aspect_ratio = max(trace.bbox_aspect_ratio, 1.0 / trace.bbox_aspect_ratio) if trace.bbox_aspect_ratio else 0.0
                if aspect_ratio > self.config.component_filter_max_aspect_ratio:
                    continue
            if self.config.component_filter_min_fill_density is not None:
                if trace.fill_density < self.config.component_filter_min_fill_density:
                    continue
            filtered.append(roi)
        return filtered

    def _expand_to_min_size(self, roi: ROI, frame_size: FrameSize) -> ROI:
        min_width = self.config.min_final_roi_width
        min_height = self.config.min_final_roi_height
        if min_width <= 0 and min_height <= 0:
            return roi
        width = max(roi.w, min_width)
        height = max(roi.h, min_height)
        center_x = roi.x + roi.w / 2.0
        center_y = roi.y + roi.h / 2.0
        x1 = round(center_x - width / 2.0)
        y1 = round(center_y - height / 2.0)
        x1 = min(max(0, x1), max(0, frame_size.width - width))
        y1 = min(max(0, y1), max(0, frame_size.height - height))
        x2 = min(frame_size.width, x1 + width)
        y2 = min(frame_size.height, y1 + height)
        return ROI(x=x1, y=y1, w=max(0, x2 - x1), h=max(0, y2 - y1), score=roi.score)


def sort_rois_by_area(rois: list[ROI]) -> list[ROI]:
    return sorted(rois, key=lambda roi: roi.area(), reverse=True)
