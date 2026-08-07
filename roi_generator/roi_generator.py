"""ROI candidate generation and coordinate conversion."""

from __future__ import annotations

from common import FrameSize, ROI


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
