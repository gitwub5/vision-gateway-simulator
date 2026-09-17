"""Velocity/scale-aware tracker prior POC metrics for traffic scenes."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common import FrameSize, GroundTruthAnnotation, ROI
from common.io import write_json, write_text
from common.records import format_ratio, group_by_frame
from evaluation.metrics.roi_containment import contains_bbox


@dataclass(frozen=True)
class VelocityTrackerFrame:
    camera_id: str
    frame_id: int
    frame_index: int
    timestamp: float
    frame_size: FrameSize


@dataclass(frozen=True)
class VelocityTrackerProfile:
    name: str
    refresh_interval: int
    ttl_frames: int
    margin_ratio: float
    use_velocity: bool
    scale_margin_ratio: float = 0.0
    max_match_distance_ratio: float = 0.12

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VelocityTrackerFrameRecord:
    camera_id: str
    frame_id: int
    frame_index: int
    profile_name: str
    is_refresh_frame: bool
    target_gt_count: int
    contained_gt_count: int
    roi_count: int
    roi_area_ratio: float
    effective_input_area_ratio: float

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VelocityTrackerProfileReport:
    profile: VelocityTrackerProfile
    frame_count: int
    refresh_frame_count: int
    memory_frame_count: int
    target_gt_count: int
    contained_gt_count: int
    memory_frame_target_gt_count: int
    memory_frame_contained_gt_count: int
    full_frame_input_pixel_area: int
    effective_input_pixel_area: float
    average_roi_count_per_memory_frame: float
    average_roi_area_ratio_per_memory_frame: float
    max_consecutive_memory_miss_frames: int

    @property
    def refresh_frame_rate(self) -> float:
        return self.refresh_frame_count / self.frame_count if self.frame_count else 0.0

    @property
    def full_frame_detector_call_reduction(self) -> float:
        return 1.0 - self.refresh_frame_rate

    @property
    def target_gt_recall(self) -> float:
        return self.contained_gt_count / self.target_gt_count if self.target_gt_count else 0.0

    @property
    def memory_frame_target_gt_recall(self) -> float:
        if self.memory_frame_target_gt_count == 0:
            return 0.0
        return self.memory_frame_contained_gt_count / self.memory_frame_target_gt_count

    @property
    def effective_input_area_ratio(self) -> float:
        if self.full_frame_input_pixel_area == 0:
            return 0.0
        return self.effective_input_pixel_area / self.full_frame_input_pixel_area

    @property
    def effective_input_area_reduction(self) -> float:
        return 1.0 - self.effective_input_area_ratio

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["profile"] = self.profile.to_json_dict()
        data["refresh_frame_rate"] = self.refresh_frame_rate
        data["full_frame_detector_call_reduction"] = self.full_frame_detector_call_reduction
        data["target_gt_recall"] = self.target_gt_recall
        data["memory_frame_target_gt_recall"] = self.memory_frame_target_gt_recall
        data["effective_input_area_ratio"] = self.effective_input_area_ratio
        data["effective_input_area_reduction"] = self.effective_input_area_reduction
        return data


@dataclass(frozen=True)
class VelocityTrackerReport:
    dataset_config: str
    experiment_name: str
    target_classes: tuple[str, ...]
    frame_count: int
    target_gt_count: int
    target_frame_count: int
    profiles: dict[str, VelocityTrackerProfileReport] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "dataset_config": self.dataset_config,
            "experiment_name": self.experiment_name,
            "target_classes": list(self.target_classes),
            "frame_count": self.frame_count,
            "target_gt_count": self.target_gt_count,
            "target_frame_count": self.target_frame_count,
            "profiles": {
                name: profile.to_json_dict()
                for name, profile in self.profiles.items()
            },
        }

    def to_markdown(self) -> str:
        lines = [
            "# Velocity / Scale-aware Tracker Prior POC Report",
            "",
            "## Scope",
            "",
            f"- Experiment: `{self.experiment_name}`",
            f"- Dataset config: `{self.dataset_config}`",
            f"- Target classes: `{', '.join(self.target_classes) if self.target_classes else 'all'}`",
            f"- Frames: {self.frame_count}",
            f"- Target frames: {self.target_frame_count}",
            f"- Target GT objects: {self.target_gt_count}",
            "",
            "## Profile Comparison",
            "",
            (
                "| Profile | Detector call reduction | Effective input reduction | "
                "GT recall | Memory-frame GT recall | ROI/memory frame | Max miss run |"
            ),
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for profile in self.profiles.values():
            lines.append(
                "| "
                f"`{profile.profile.name}` | "
                f"{format_ratio(profile.full_frame_detector_call_reduction)} | "
                f"{format_ratio(profile.effective_input_area_reduction)} | "
                f"{format_ratio(profile.target_gt_recall)} | "
                f"{format_ratio(profile.memory_frame_target_gt_recall)} | "
                f"{profile.average_roi_count_per_memory_frame:.3f} | "
                f"{profile.max_consecutive_memory_miss_frames} |"
            )
        lines.append("")
        return "\n".join(lines)


@dataclass
class _TrackState:
    track_id: int
    class_name: str
    previous_bbox: list[float] | None
    previous_frame_index: int | None
    last_bbox: list[float]
    last_frame_index: int
    last_roi: ROI


def default_velocity_tracker_profiles() -> list[VelocityTrackerProfile]:
    return [
        VelocityTrackerProfile(
            name="hold_refresh_5_margin_30",
            refresh_interval=5,
            ttl_frames=5,
            margin_ratio=0.30,
            use_velocity=False,
        ),
        VelocityTrackerProfile(
            name="velocity_refresh_5_margin_30",
            refresh_interval=5,
            ttl_frames=5,
            margin_ratio=0.30,
            use_velocity=True,
        ),
        VelocityTrackerProfile(
            name="velocity_refresh_5_margin_50",
            refresh_interval=5,
            ttl_frames=5,
            margin_ratio=0.50,
            use_velocity=True,
        ),
        VelocityTrackerProfile(
            name="velocity_scale_refresh_5_margin_30",
            refresh_interval=5,
            ttl_frames=5,
            margin_ratio=0.30,
            use_velocity=True,
            scale_margin_ratio=0.35,
        ),
        VelocityTrackerProfile(
            name="velocity_scale_refresh_10_margin_50",
            refresh_interval=10,
            ttl_frames=10,
            margin_ratio=0.50,
            use_velocity=True,
            scale_margin_ratio=0.35,
        ),
    ]


def build_velocity_tracker_report(
    frames: Iterable[VelocityTrackerFrame],
    ground_truth: Iterable[GroundTruthAnnotation],
    profiles: Iterable[VelocityTrackerProfile],
    dataset_config: str,
    experiment_name: str,
    target_classes: Iterable[str] | None = None,
) -> tuple[VelocityTrackerReport, list[VelocityTrackerFrameRecord]]:
    frame_records = list(frames)
    gt_records = list(ground_truth)
    gt_by_frame = group_by_frame(gt_records)
    reports: dict[str, VelocityTrackerProfileReport] = {}
    all_records: list[VelocityTrackerFrameRecord] = []
    for profile in profiles:
        report, records = evaluate_velocity_tracker_profile(frame_records, gt_by_frame, profile)
        reports[profile.name] = report
        all_records.extend(records)
    target_frames = {key for key, records in gt_by_frame.items() if records}
    return (
        VelocityTrackerReport(
            dataset_config=dataset_config,
            experiment_name=experiment_name,
            target_classes=tuple(target_classes or ()),
            frame_count=len(frame_records),
            target_gt_count=len(gt_records),
            target_frame_count=len(target_frames),
            profiles=reports,
        ),
        all_records,
    )


def evaluate_velocity_tracker_profile(
    frames: list[VelocityTrackerFrame],
    gt_by_frame: dict[tuple[str, int], list[GroundTruthAnnotation]],
    profile: VelocityTrackerProfile,
) -> tuple[VelocityTrackerProfileReport, list[VelocityTrackerFrameRecord]]:
    tracks: list[_TrackState] = []
    next_track_id = 1
    records: list[VelocityTrackerFrameRecord] = []
    full_frame_area = sum(frame.frame_size.area() for frame in frames)
    effective_area = 0.0
    refresh_count = 0
    gt_total = 0
    contained_total = 0
    memory_gt_total = 0
    memory_contained_total = 0
    roi_counts: list[int] = []
    roi_area_ratios: list[float] = []
    miss_runs: list[int] = []
    current_miss_run = 0

    for frame in frames:
        frame_gt = gt_by_frame.get((frame.camera_id, frame.frame_id), [])
        is_refresh = frame.frame_index % max(1, profile.refresh_interval) == 0
        if is_refresh:
            refresh_count += 1
            tracks, next_track_id = _refresh_tracks(
                tracks=tracks,
                frame_gt=frame_gt,
                frame=frame,
                profile=profile,
                next_track_id=next_track_id,
            )
            contained = len(frame_gt)
            frame_effective_area = frame.frame_size.area()
            if current_miss_run:
                miss_runs.append(current_miss_run)
                current_miss_run = 0
        else:
            frame_rois = [
                _predict_track_roi(track, frame.frame_index, frame.frame_size, profile)
                for track in tracks
                if frame.frame_index - track.last_frame_index <= profile.ttl_frames
            ]
            contained = sum(1 for gt in frame_gt if any(contains_bbox(roi, gt.bbox_xyxy) for roi in frame_rois))
            memory_gt_total += len(frame_gt)
            memory_contained_total += contained
            frame_effective_area = _union_area(frame_rois)
            roi_counts.append(len(frame_rois))
            area_ratio = frame_effective_area / frame.frame_size.area() if frame.frame_size.area() else 0.0
            roi_area_ratios.append(area_ratio)
            if frame_gt and contained < len(frame_gt):
                current_miss_run += 1
            elif current_miss_run:
                miss_runs.append(current_miss_run)
                current_miss_run = 0
        gt_total += len(frame_gt)
        contained_total += contained
        effective_area += frame_effective_area
        records.append(
            VelocityTrackerFrameRecord(
                camera_id=frame.camera_id,
                frame_id=frame.frame_id,
                frame_index=frame.frame_index,
                profile_name=profile.name,
                is_refresh_frame=is_refresh,
                target_gt_count=len(frame_gt),
                contained_gt_count=contained,
                roi_count=len(tracks) if not is_refresh else len(frame_gt),
                roi_area_ratio=(
                    frame_effective_area / frame.frame_size.area()
                    if frame.frame_size.area()
                    else 0.0
                ),
                effective_input_area_ratio=(
                    frame_effective_area / frame.frame_size.area()
                    if frame.frame_size.area()
                    else 0.0
                ),
            )
        )
    if current_miss_run:
        miss_runs.append(current_miss_run)

    return (
        VelocityTrackerProfileReport(
            profile=profile,
            frame_count=len(frames),
            refresh_frame_count=refresh_count,
            memory_frame_count=max(0, len(frames) - refresh_count),
            target_gt_count=gt_total,
            contained_gt_count=contained_total,
            memory_frame_target_gt_count=memory_gt_total,
            memory_frame_contained_gt_count=memory_contained_total,
            full_frame_input_pixel_area=full_frame_area,
            effective_input_pixel_area=effective_area,
            average_roi_count_per_memory_frame=_average(roi_counts),
            average_roi_area_ratio_per_memory_frame=_average(roi_area_ratios),
            max_consecutive_memory_miss_frames=max(miss_runs) if miss_runs else 0,
        ),
        records,
    )


def write_velocity_tracker_report_json(report: VelocityTrackerReport, output_path: str | Path) -> None:
    write_json(report.to_json_dict(), output_path)


def write_velocity_tracker_report_markdown(report: VelocityTrackerReport, output_path: str | Path) -> None:
    write_text(report.to_markdown(), output_path)


def _refresh_tracks(
    tracks: list[_TrackState],
    frame_gt: list[GroundTruthAnnotation],
    frame: VelocityTrackerFrame,
    profile: VelocityTrackerProfile,
    next_track_id: int,
) -> tuple[list[_TrackState], int]:
    available = tracks[:]
    refreshed: list[_TrackState] = []
    diagonal = (frame.frame_size.width**2 + frame.frame_size.height**2) ** 0.5
    max_distance = diagonal * profile.max_match_distance_ratio
    for gt in frame_gt:
        match_index = _nearest_track_index(available, gt, max_distance)
        if match_index is None:
            roi = _roi_from_bbox(gt.bbox_xyxy, frame.frame_size, profile.margin_ratio, profile.scale_margin_ratio)
            refreshed.append(
                _TrackState(
                    track_id=next_track_id,
                    class_name=gt.class_name,
                    previous_bbox=None,
                    previous_frame_index=None,
                    last_bbox=list(gt.bbox_xyxy),
                    last_frame_index=frame.frame_index,
                    last_roi=roi,
                )
            )
            next_track_id += 1
        else:
            matched = available.pop(match_index)
            roi = _roi_from_bbox(gt.bbox_xyxy, frame.frame_size, profile.margin_ratio, profile.scale_margin_ratio)
            refreshed.append(
                _TrackState(
                    track_id=matched.track_id,
                    class_name=gt.class_name,
                    previous_bbox=matched.last_bbox,
                    previous_frame_index=matched.last_frame_index,
                    last_bbox=list(gt.bbox_xyxy),
                    last_frame_index=frame.frame_index,
                    last_roi=roi,
                )
            )
    return refreshed, next_track_id


def _nearest_track_index(
    tracks: list[_TrackState],
    gt: GroundTruthAnnotation,
    max_distance: float,
) -> int | None:
    gt_center = _bbox_center(gt.bbox_xyxy)
    best_index: int | None = None
    best_distance = max_distance
    for index, track in enumerate(tracks):
        if track.class_name != gt.class_name:
            continue
        track_center = _bbox_center(track.last_bbox)
        distance = ((gt_center[0] - track_center[0]) ** 2 + (gt_center[1] - track_center[1]) ** 2) ** 0.5
        if distance <= best_distance:
            best_index = index
            best_distance = distance
    return best_index


def _predict_track_roi(
    track: _TrackState,
    frame_index: int,
    frame_size: FrameSize,
    profile: VelocityTrackerProfile,
) -> ROI:
    if not profile.use_velocity or track.previous_bbox is None or track.previous_frame_index is None:
        return track.last_roi
    delta_frames = max(1, track.last_frame_index - track.previous_frame_index)
    step = frame_index - track.last_frame_index
    dx1 = (track.last_bbox[0] - track.previous_bbox[0]) / delta_frames * step
    dy1 = (track.last_bbox[1] - track.previous_bbox[1]) / delta_frames * step
    dx2 = (track.last_bbox[2] - track.previous_bbox[2]) / delta_frames * step
    dy2 = (track.last_bbox[3] - track.previous_bbox[3]) / delta_frames * step
    predicted = [
        track.last_bbox[0] + dx1,
        track.last_bbox[1] + dy1,
        track.last_bbox[2] + dx2,
        track.last_bbox[3] + dy2,
    ]
    return _roi_from_bbox(predicted, frame_size, profile.margin_ratio, profile.scale_margin_ratio)


def _roi_from_bbox(
    bbox: list[float],
    frame_size: FrameSize,
    margin_ratio: float,
    scale_margin_ratio: float,
) -> ROI:
    x1, y1, x2, y2 = bbox
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)
    bbox_area_ratio = (width * height) / frame_size.area() if frame_size.area() else 0.0
    small_object_boost = scale_margin_ratio * max(0.0, 0.02 - bbox_area_ratio) / 0.02
    margin_x = width * (margin_ratio + small_object_boost)
    margin_y = height * (margin_ratio + small_object_boost)
    left = max(0, int(x1 - margin_x))
    top = max(0, int(y1 - margin_y))
    right = min(frame_size.width, int(x2 + margin_x))
    bottom = min(frame_size.height, int(y2 + margin_y))
    return ROI(x=left, y=top, w=max(0, right - left), h=max(0, bottom - top))


def _union_area(rois: list[ROI]) -> int:
    if not rois:
        return 0
    xs = sorted({roi.x for roi in rois} | {roi.x + roi.w for roi in rois})
    area = 0
    for x_left, x_right in zip(xs, xs[1:]):
        if x_right <= x_left:
            continue
        intervals = sorted((roi.y, roi.y + roi.h) for roi in rois if roi.x < x_right and roi.x + roi.w > x_left)
        merged: list[tuple[int, int]] = []
        for start, end in intervals:
            if not merged or start > merged[-1][1]:
                merged.append((start, end))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        covered_y = sum(max(0, end - start) for start, end in merged)
        area += (x_right - x_left) * covered_y
    return area


def _bbox_center(bbox: list[float]) -> tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0


def _average(values: list[float] | list[int]) -> float:
    return sum(values) / len(values) if values else 0.0
