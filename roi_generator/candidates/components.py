"""Connected-component ROI candidate generation."""

from __future__ import annotations

from common import FrameSize, ROI
from roi_generator.observability.trace import ComponentTrace


def generate_roi_candidates(motion_map, min_area_ratio: float = 0.001) -> list[ROI]:
    import cv2

    height, width = motion_map.shape[:2]
    min_area = width * height * min_area_ratio
    count, _, stats, _ = cv2.connectedComponentsWithStats(motion_map, connectivity=8)

    rois: list[ROI] = []
    for label in range(1, count):
        x, y, w, h, area = stats[label]
        if area < min_area:
            continue
        score = min(float(area) / float(width * height), 1.0)
        rois.append(ROI(x=int(x), y=int(y), w=int(w), h=int(h), score=score, coord_system="analysis_frame"))
    return rois


def count_connected_components(motion_map) -> int:
    import cv2

    count, _, _, _ = cv2.connectedComponentsWithStats(motion_map, connectivity=8)
    return max(0, int(count) - 1)


def motion_density(motion_map) -> float:
    area = max(1, int(motion_map.size))
    try:
        active = int((motion_map > 0).sum())
    except TypeError:
        return 0.0
    return active / area


def component_traces_from_rois(rois: list[ROI], frame_size: FrameSize) -> list[ComponentTrace]:
    frame_area = frame_size.area()
    traces: list[ComponentTrace] = []
    for index, roi in enumerate(rois, start=1):
        component_area_ratio = max(0.0, min(roi.score, 1.0))
        component_area = component_area_ratio * frame_area
        bbox_area = roi.area()
        traces.append(
            ComponentTrace(
                component_id=index,
                bbox=roi,
                component_area_ratio=component_area_ratio,
                bbox_width=roi.w,
                bbox_height=roi.h,
                bbox_aspect_ratio=_aspect_ratio(roi),
                fill_density=(component_area / bbox_area if bbox_area else 0.0),
                center_x=roi.x + roi.w / 2.0,
                center_y=roi.y + roi.h / 2.0,
            )
        )
    return traces


def scale_roi_to_original(roi: ROI, analysis_size: FrameSize, original_size: FrameSize) -> ROI:
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


def add_margin_and_clip(roi: ROI, frame_size: FrameSize, margin_ratio: float) -> ROI:
    margin_x = round(roi.w * margin_ratio)
    margin_y = round(roi.h * margin_ratio)
    x1 = max(0, roi.x - margin_x)
    y1 = max(0, roi.y - margin_y)
    x2 = min(frame_size.width, roi.x + roi.w + margin_x)
    y2 = min(frame_size.height, roi.y + roi.h + margin_y)
    return ROI(x=x1, y=y1, w=max(0, x2 - x1), h=max(0, y2 - y1), score=roi.score)


def merge_rois(rois: list[ROI], distance_ratio: float, frame_size: FrameSize) -> list[ROI]:
    if not rois:
        return []

    distance = max(frame_size.width, frame_size.height) * distance_ratio
    merged: list[ROI] = []
    pending = rois[:]

    while pending:
        current = pending.pop(0)
        changed = True
        while changed:
            changed = False
            remaining: list[ROI] = []
            for candidate in pending:
                if _should_merge(current, candidate, distance):
                    current = _union(current, candidate)
                    changed = True
                else:
                    remaining.append(candidate)
            pending = remaining
        merged.append(current)
    return merged


def _should_merge(a: ROI, b: ROI, distance: float) -> bool:
    ax2 = a.x + a.w
    ay2 = a.y + a.h
    bx2 = b.x + b.w
    by2 = b.y + b.h
    return not (ax2 + distance < b.x or bx2 + distance < a.x or ay2 + distance < b.y or by2 + distance < a.y)


def _union(a: ROI, b: ROI) -> ROI:
    x1 = min(a.x, b.x)
    y1 = min(a.y, b.y)
    x2 = max(a.x + a.w, b.x + b.w)
    y2 = max(a.y + a.h, b.y + b.h)
    return ROI(x=x1, y=y1, w=x2 - x1, h=y2 - y1, score=max(a.score, b.score), coord_system=a.coord_system)


def _aspect_ratio(roi: ROI) -> float:
    if roi.h <= 0:
        return 0.0
    return roi.w / roi.h
