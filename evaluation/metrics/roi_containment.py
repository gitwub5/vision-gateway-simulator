"""ROI containment metrics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from common import Detection, FrameSize, GateFrameMetadata, ROI, ROIMetadata


def contains_bbox(roi: ROI, bbox_xyxy: list[float]) -> bool:
    x1, y1, x2, y2 = bbox_xyxy
    return roi.x <= x1 and roi.y <= y1 and roi.x + roi.w >= x2 and roi.y + roi.h >= y2


@dataclass(frozen=True)
class RoiContainmentSummary:
    reference_detection_count: int
    contained_detection_count: int
    roi_record_count: int
    frame_count: int
    average_roi_count: float
    average_roi_area_ratio: float

    @property
    def containment_rate(self) -> float:
        if self.reference_detection_count == 0:
            return 0.0
        return self.contained_detection_count / self.reference_detection_count

    def to_json_dict(self) -> dict:
        return {
            "reference_detection_count": self.reference_detection_count,
            "contained_detection_count": self.contained_detection_count,
            "roi_record_count": self.roi_record_count,
            "frame_count": self.frame_count,
            "containment_rate": self.containment_rate,
            "average_roi_count": self.average_roi_count,
            "average_roi_area_ratio": self.average_roi_area_ratio,
        }


def summarize_roi_containment(
    reference_detections: Iterable[Detection],
    roi_records: Iterable[ROIMetadata],
    frame_records: Iterable[GateFrameMetadata],
) -> RoiContainmentSummary:
    references = list(reference_detections)
    rois = list(roi_records)
    frames = list(frame_records)
    rois_by_frame = _group_rois_by_frame(rois)

    contained_count = 0
    for detection in references:
        frame_rois = rois_by_frame.get((detection.camera_id, detection.frame_id), [])
        if any(contains_bbox(roi_record.roi, detection.bbox_xyxy) for roi_record in frame_rois):
            contained_count += 1

    frame_count = len(frames) if frames else _infer_frame_count_from_rois(rois)
    average_roi_count = len(rois) / frame_count if frame_count else 0.0
    average_roi_area_ratio = _average_roi_area_ratio(rois)

    return RoiContainmentSummary(
        reference_detection_count=len(references),
        contained_detection_count=contained_count,
        roi_record_count=len(rois),
        frame_count=frame_count,
        average_roi_count=average_roi_count,
        average_roi_area_ratio=average_roi_area_ratio,
    )


def _group_rois_by_frame(records: list[ROIMetadata]) -> dict[tuple[str, int], list[ROIMetadata]]:
    grouped: dict[tuple[str, int], list[ROIMetadata]] = {}
    for record in records:
        grouped.setdefault((record.camera_id, record.frame_id), []).append(record)
    return grouped


def _infer_frame_count_from_rois(records: list[ROIMetadata]) -> int:
    return len({(record.camera_id, record.frame_id) for record in records})


def _average_roi_area_ratio(records: list[ROIMetadata]) -> float:
    if not records:
        return 0.0
    ratios = []
    for record in records:
        frame_area = _frame_area(record.original_frame_size)
        ratios.append(record.roi.area() / frame_area if frame_area > 0 else 0.0)
    return sum(ratios) / len(ratios)


def _frame_area(frame_size: FrameSize) -> int:
    return frame_size.area()
