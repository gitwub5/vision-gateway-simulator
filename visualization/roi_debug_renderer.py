"""Render per-frame ROI generator debug sheets."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from common import GroundTruthAnnotation, ROI
from common.records import frame_key, group_by_frame
from evaluation.metrics.class_filter import filter_gt_by_target_classes
from roi_generator.core.gate import RoiDebugSnapshot
from visualization.primitives import (
    COLOR_COMPONENT,
    COLOR_FEEDBACK,
    COLOR_MERGED,
    COLOR_ROI,
    COLOR_TILE,
    blank_panel,
    clear_images,
    draw_gt,
    draw_roi,
    draw_title,
    frame_stem,
    load_visualization_dependencies,
)


class RoiDebugRenderer:
    def __init__(
        self,
        output_dir: str | Path,
        ground_truth: Iterable[GroundTruthAnnotation] | None = None,
        target_classes: tuple[str, ...] = (),
        stride: int = 1,
        max_frames: int | None = None,
        clear_existing: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if clear_existing:
            clear_images(self.output_dir)
        self.cv2, self.np = load_visualization_dependencies()
        self.stride = max(1, int(stride))
        self.max_frames = max_frames
        self.seen_frames = 0
        self.rendered_frames = 0
        gt_records = filter_gt_by_target_classes(ground_truth or [], target_classes)
        self.gt_by_frame = group_by_frame(gt_records)

    def write(self, snapshot: RoiDebugSnapshot) -> None:
        self.seen_frames += 1
        if self.max_frames is not None and self.rendered_frames >= self.max_frames:
            return
        if (self.seen_frames - 1) % self.stride != 0:
            return

        image = draw_roi_debug_sheet(
            cv2=self.cv2,
            np=self.np,
            snapshot=snapshot,
            target_gt=self.gt_by_frame.get(frame_key(snapshot.packet.camera_id, snapshot.packet.frame_id), []),
        )
        stem = frame_stem(snapshot.packet.camera_id, snapshot.packet.frame_id)
        self.cv2.imwrite(str(self.output_dir / f"{stem}_roi_debug.jpg"), image)
        self.rendered_frames += 1

    def summary(self) -> dict[str, int | str]:
        return {
            "seen_frames": self.seen_frames,
            "rendered_frames": self.rendered_frames,
            "output_dir": str(self.output_dir),
        }


def draw_roi_debug_sheet(cv2: Any, np: Any, snapshot: RoiDebugSnapshot, target_gt: list[GroundTruthAnnotation]) -> Any:
    packet = snapshot.packet
    original_panel = packet.frame.copy()
    final_panel = packet.frame.copy()
    candidate_panel = packet.frame.copy()
    summary_panel = blank_panel(cv2, packet.frame, "ROI Debug Summary")
    policy_panel = draw_policy_panel(cv2, packet.frame, snapshot)

    draw_title(cv2, original_panel, "Original + Target GT")
    draw_title(cv2, final_panel, "Final ROI")
    draw_title(cv2, candidate_panel, "Candidate/Merged ROI")

    for gt in target_gt:
        draw_gt(cv2, original_panel, gt, label_prefix="target")
        draw_gt(cv2, final_panel, gt, label_prefix="target")
    for roi in snapshot.decision.rois:
        draw_roi(cv2, final_panel, roi, COLOR_ROI, "final")

    draw_analysis_rois(cv2, candidate_panel, snapshot)
    draw_summary(cv2, summary_panel, snapshot, target_gt)

    analysis_gray = gray_to_bgr(cv2, snapshot.analysis_gray)
    draw_title(cv2, analysis_gray, "Analysis Gray")
    absdiff_panel = absdiff_heatmap(cv2, snapshot)
    raw_motion_panel = map_to_bgr(cv2, snapshot.event_maps.motion_map if snapshot.event_maps else None, "Raw Motion Map")
    filtered_motion_panel = map_to_bgr(cv2, snapshot.generation_trace.filtered_motion_map, "Filtered Motion Map")

    top = np.concatenate([original_panel, final_panel, candidate_panel], axis=1)
    middle = np.concatenate(
        [
            resize_to_original(cv2, analysis_gray, packet.frame),
            resize_to_original(cv2, absdiff_panel, packet.frame),
            resize_to_original(cv2, raw_motion_panel, packet.frame),
        ],
        axis=1,
    )
    bottom = np.concatenate(
        [
            resize_to_original(cv2, filtered_motion_panel, packet.frame),
            policy_panel,
            summary_panel,
        ],
        axis=1,
    )
    return np.concatenate([top, middle, bottom], axis=0)


def draw_analysis_rois(cv2: Any, canvas: Any, snapshot: RoiDebugSnapshot) -> None:
    analysis_size = snapshot.decision.analysis_frame_size
    original_size = snapshot.decision.original_frame_size
    for tile in snapshot.generation_trace.tile_traces:
        if tile.selected:
            draw_roi(cv2, canvas, tile.bbox, COLOR_TILE, "tile")
    for roi in snapshot.generation_trace.candidate_analysis_rois:
        scaled = scale_analysis_roi(roi, analysis_size, original_size)
        draw_roi(cv2, canvas, scaled, COLOR_COMPONENT, "candidate")
    for roi in snapshot.generation_trace.merged_analysis_rois:
        scaled = scale_analysis_roi(roi, analysis_size, original_size)
        draw_roi(cv2, canvas, scaled, COLOR_MERGED, "merged")
    for roi in snapshot.generation_trace.final_rois:
        draw_roi(cv2, canvas, roi, COLOR_ROI, "final")


def draw_policy_panel(cv2: Any, frame: Any, snapshot: RoiDebugSnapshot) -> Any:
    policy = snapshot.decision.policy_label
    panel = frame.copy()
    if debug_panel_kind(policy) == "tile":
        draw_title(cv2, panel, "Selected Tile Trace")
        for tile in snapshot.generation_trace.tile_traces:
            if tile.selected:
                draw_roi(cv2, panel, tile.bbox, COLOR_TILE, f"tile {tile.row},{tile.col}")
    else:
        draw_title(cv2, panel, "Filtered Components")
        analysis_size = snapshot.decision.analysis_frame_size
        original_size = snapshot.decision.original_frame_size
        for component in snapshot.generation_trace.component_traces:
            scaled = scale_analysis_roi(component.bbox, analysis_size, original_size)
            draw_roi(cv2, panel, scaled, COLOR_COMPONENT, f"component {component.component_id}")
    for roi in snapshot.feedback_rois:
        draw_roi(cv2, panel, roi, COLOR_FEEDBACK, "feedback")
    return panel


def debug_panel_kind(policy_label: str) -> str:
    return "tile" if policy_label in {"tile_mask", "hybrid_component_tile"} else "component"


def draw_summary(cv2: Any, panel: Any, snapshot: RoiDebugSnapshot, target_gt: list[GroundTruthAnnotation]) -> None:
    trace = snapshot.generation_trace
    config = snapshot.config
    frame_area = snapshot.decision.original_frame_size.area()
    final_area = sum(roi.area() for roi in trace.final_rois)
    decision_area = sum(roi.area() for roi in snapshot.decision.rois)
    lines = [
        f"frame: {snapshot.packet.camera_id} #{snapshot.packet.frame_id}",
        f"trigger: {snapshot.decision.trigger_type}",
        f"full_frame_check: {snapshot.decision.should_run_full_frame}",
        f"budget_fallback: {snapshot.budget_fallback.reason or 'none'}",
        f"target_gt: {len(target_gt)}",
        f"analysis_size: {snapshot.decision.analysis_frame_size.as_list()}",
        f"thresholds motion/on/off: {config.threshold_motion}/{config.threshold_on}/{config.threshold_off}",
        f"morph_kernel: {config.morphology_kernel_size}",
        f"min_area_ratio: {config.min_area_ratio}",
        f"candidate_rois: {len(trace.candidate_analysis_rois)}",
        f"selected_tiles: {sum(1 for tile in trace.tile_traces if tile.selected)}",
        f"merged_rois: {len(trace.merged_analysis_rois)}",
        f"final_rois_before_policy: {len(trace.final_rois)}",
        f"decision_rois: {len(snapshot.decision.rois)}",
        f"feedback_rois: {len(snapshot.feedback_rois)}",
        f"final_area_ratio_before_policy: {(final_area / frame_area if frame_area else 0.0):.3f}",
        f"decision_area_ratio: {(decision_area / frame_area if frame_area else 0.0):.3f}",
    ]
    for index, line in enumerate(lines):
        cv2.putText(panel, line, (12, 42 + index * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (235, 235, 235), 1, cv2.LINE_AA)


def gray_to_bgr(cv2: Any, gray: Any) -> Any:
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def absdiff_heatmap(cv2: Any, snapshot: RoiDebugSnapshot) -> Any:
    if snapshot.previous_analysis_gray is None:
        return map_to_bgr(cv2, None, "Absdiff Heatmap")
    diff = cv2.absdiff(snapshot.analysis_gray, snapshot.previous_analysis_gray)
    colored = cv2.applyColorMap(diff, cv2.COLORMAP_JET)
    draw_title(cv2, colored, "Absdiff Heatmap")
    return colored


def map_to_bgr(cv2: Any, map_image: Any | None, title: str) -> Any:
    if map_image is None:
        import numpy as np

        canvas = np.zeros((144, 256, 3), dtype="uint8")
    else:
        canvas = cv2.cvtColor(map_image, cv2.COLOR_GRAY2BGR)
    draw_title(cv2, canvas, title)
    return canvas


def resize_to_original(cv2: Any, image: Any, original_frame: Any) -> Any:
    height, width = original_frame.shape[:2]
    return cv2.resize(image, (width, height))


def scale_analysis_roi(roi: ROI, analysis_size, original_size) -> ROI:
    scale_x = original_size.width / analysis_size.width
    scale_y = original_size.height / analysis_size.height
    return ROI(
        x=round(roi.x * scale_x),
        y=round(roi.y * scale_y),
        w=round(roi.w * scale_x),
        h=round(roi.h * scale_y),
        score=roi.score,
        coord_system="original_frame",
    )
