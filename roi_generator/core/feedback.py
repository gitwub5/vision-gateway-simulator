"""Reference detector feedback cache for ROI proposal."""

from __future__ import annotations

from dataclasses import dataclass

from common import Detection, FrameSize, ROI
from roi_generator.core.config import RoiGeneratorConfig


@dataclass(frozen=True)
class ReferenceFeedbackCandidate:
    detection: Detection
    roi: ROI
    age_frames: int


@dataclass(frozen=True)
class ReferenceFeedbackResult:
    candidates: list[ReferenceFeedbackCandidate]
    active_track_count: int
    stale_track_count: int


class ReferenceFeedbackCache:
    """Stores recent full-frame detector boxes for later ROI proposals."""

    def __init__(self) -> None:
        self._tracks: dict[tuple[str, int, str], Detection] = {}

    def update(self, detections: list[Detection], config: RoiGeneratorConfig) -> None:
        if not config.reference_feedback_enabled:
            return
        for detection in detections:
            if detection.confidence < config.reference_feedback_min_confidence:
                continue
            self._tracks[self._track_key(detection)] = detection

    def candidates(
        self,
        camera_id: str,
        frame_id: int,
        frame_size: FrameSize,
        config: RoiGeneratorConfig,
    ) -> ReferenceFeedbackResult:
        if not config.reference_feedback_enabled:
            return ReferenceFeedbackResult(candidates=[], active_track_count=0, stale_track_count=0)

        active: list[ReferenceFeedbackCandidate] = []
        stale_keys: list[tuple[str, int, str]] = []
        for key, detection in self._tracks.items():
            if detection.camera_id != camera_id:
                continue
            age_frames = frame_id - detection.frame_id
            if age_frames < 0:
                continue
            if age_frames > config.reference_feedback_ttl_frames:
                stale_keys.append(key)
                continue
            active.append(
                ReferenceFeedbackCandidate(
                    detection=detection,
                    roi=_roi_from_detection(detection, frame_size, config.reference_feedback_margin_ratio),
                    age_frames=age_frames,
                )
            )

        for key in stale_keys:
            self._tracks.pop(key, None)

        active.sort(key=lambda candidate: candidate.detection.confidence, reverse=True)
        if config.reference_feedback_max_candidates_per_frame > 0:
            active = active[: config.reference_feedback_max_candidates_per_frame]
        return ReferenceFeedbackResult(
            candidates=active,
            active_track_count=len(active),
            stale_track_count=len(stale_keys),
        )

    @staticmethod
    def _track_key(detection: Detection) -> tuple[str, int, str]:
        return (
            detection.camera_id,
            detection.class_id,
            detection.roi_id or f"{detection.class_name}:{detection.bbox_xyxy}",
        )


def _roi_from_detection(detection: Detection, frame_size: FrameSize, margin_ratio: float) -> ROI:
    x1, y1, x2, y2 = detection.bbox_xyxy
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    pad_x = width * margin_ratio
    pad_y = height * margin_ratio
    clipped_x1 = max(0, round(x1 - pad_x))
    clipped_y1 = max(0, round(y1 - pad_y))
    clipped_x2 = min(frame_size.width, round(x2 + pad_x))
    clipped_y2 = min(frame_size.height, round(y2 + pad_y))
    return ROI(
        x=clipped_x1,
        y=clipped_y1,
        w=max(0, clipped_x2 - clipped_x1),
        h=max(0, clipped_y2 - clipped_y1),
        score=detection.confidence,
        coord_system="original_frame",
    )
