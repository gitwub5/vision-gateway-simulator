"""Temporal gate POC metrics for frame-level GPU workload reduction."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common.io import write_json, write_text
from common.records import format_ratio


@dataclass(frozen=True)
class TemporalFrameRecord:
    camera_id: str
    frame_id: int
    timestamp: float
    frame_index: int
    has_target: bool
    target_gt_count: int
    scene_delta_mean: float
    scene_delta_p95: float

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TemporalGateProfile:
    name: str
    mode: str
    interval: int = 1
    scene_delta_threshold: float = 0.0
    max_refresh_interval: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TemporalGateProfileReport:
    profile: TemporalGateProfile
    frame_count: int
    processed_frame_count: int
    skipped_frame_count: int
    target_frame_count: int
    processed_target_frame_count: int
    skipped_target_frame_count: int
    target_gt_count: int
    processed_target_gt_count: int
    skipped_target_gt_count: int
    max_skip_run_frames: int
    max_target_skip_run_frames: int
    mean_target_skip_run_frames: float

    @property
    def detector_call_reduction(self) -> float:
        if self.frame_count == 0:
            return 0.0
        return self.skipped_frame_count / self.frame_count

    @property
    def target_frame_recall(self) -> float:
        if self.target_frame_count == 0:
            return 0.0
        return self.processed_target_frame_count / self.target_frame_count

    @property
    def target_gt_recall(self) -> float:
        if self.target_gt_count == 0:
            return 0.0
        return self.processed_target_gt_count / self.target_gt_count

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["profile"] = self.profile.to_json_dict()
        data["detector_call_reduction"] = self.detector_call_reduction
        data["target_frame_recall"] = self.target_frame_recall
        data["target_gt_recall"] = self.target_gt_recall
        return data


@dataclass(frozen=True)
class TemporalGateReport:
    dataset_config: str
    experiment_name: str
    target_classes: tuple[str, ...]
    frame_count: int
    target_frame_count: int
    target_gt_count: int
    scene_delta_mean_average: float
    scene_delta_p95_average: float
    profiles: dict[str, TemporalGateProfileReport] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "dataset_config": self.dataset_config,
            "experiment_name": self.experiment_name,
            "target_classes": list(self.target_classes),
            "frame_count": self.frame_count,
            "target_frame_count": self.target_frame_count,
            "target_gt_count": self.target_gt_count,
            "scene_delta_mean_average": self.scene_delta_mean_average,
            "scene_delta_p95_average": self.scene_delta_p95_average,
            "profiles": {
                name: profile.to_json_dict()
                for name, profile in self.profiles.items()
            },
        }

    def to_markdown(self) -> str:
        lines = [
            "# Temporal Gate POC Report",
            "",
            "## Scope",
            "",
            f"- Experiment: `{self.experiment_name}`",
            f"- Dataset config: `{self.dataset_config}`",
            f"- Target classes: `{', '.join(self.target_classes) if self.target_classes else 'all'}`",
            f"- Frames: {self.frame_count}",
            f"- Target frames: {self.target_frame_count}",
            f"- Target GT objects: {self.target_gt_count}",
            f"- Average scene delta mean: {self.scene_delta_mean_average:.6f}",
            f"- Average scene delta p95: {self.scene_delta_p95_average:.6f}",
            "",
            "## Profile Comparison",
            "",
            (
                "| Profile | Detector call reduction | Target-frame recall | "
                "Target-GT recall | Skipped target frames | Max target skip run |"
            ),
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for profile in self.profiles.values():
            lines.append(
                "| "
                f"`{profile.profile.name}` | "
                f"{format_ratio(profile.detector_call_reduction)} | "
                f"{format_ratio(profile.target_frame_recall)} | "
                f"{format_ratio(profile.target_gt_recall)} | "
                f"{profile.skipped_target_frame_count} | "
                f"{profile.max_target_skip_run_frames} |"
            )
        lines.append("")
        return "\n".join(lines)


def default_temporal_gate_profiles() -> list[TemporalGateProfile]:
    return [
        TemporalGateProfile(name="process_all", mode="all"),
        TemporalGateProfile(name="fixed_skip_2", mode="fixed_interval", interval=2),
        TemporalGateProfile(name="fixed_skip_5", mode="fixed_interval", interval=5),
        TemporalGateProfile(name="fixed_skip_10", mode="fixed_interval", interval=10),
        TemporalGateProfile(
            name="stability_0_01_refresh_30",
            mode="scene_delta",
            scene_delta_threshold=0.01,
            max_refresh_interval=30,
        ),
        TemporalGateProfile(
            name="stability_0_02_refresh_30",
            mode="scene_delta",
            scene_delta_threshold=0.02,
            max_refresh_interval=30,
        ),
        TemporalGateProfile(
            name="stability_0_05_refresh_30",
            mode="scene_delta",
            scene_delta_threshold=0.05,
            max_refresh_interval=30,
        ),
    ]


def build_temporal_gate_report(
    records: Iterable[TemporalFrameRecord],
    profiles: Iterable[TemporalGateProfile],
    dataset_config: str,
    experiment_name: str,
    target_classes: Iterable[str] | None = None,
) -> TemporalGateReport:
    frame_records = list(records)
    profile_reports = {
        profile.name: evaluate_temporal_gate_profile(frame_records, profile)
        for profile in profiles
    }
    target_frames = [record for record in frame_records if record.has_target]
    return TemporalGateReport(
        dataset_config=dataset_config,
        experiment_name=experiment_name,
        target_classes=tuple(target_classes or ()),
        frame_count=len(frame_records),
        target_frame_count=len(target_frames),
        target_gt_count=sum(record.target_gt_count for record in frame_records),
        scene_delta_mean_average=_average(record.scene_delta_mean for record in frame_records),
        scene_delta_p95_average=_average(record.scene_delta_p95 for record in frame_records),
        profiles=profile_reports,
    )


def evaluate_temporal_gate_profile(
    records: list[TemporalFrameRecord],
    profile: TemporalGateProfile,
) -> TemporalGateProfileReport:
    processed_flags: list[bool] = []
    last_processed_index: int | None = None
    for record in records:
        should_process = _should_process(record, profile, last_processed_index)
        processed_flags.append(should_process)
        if should_process:
            last_processed_index = record.frame_index

    processed_frame_count = sum(1 for item in processed_flags if item)
    skipped_frame_count = len(records) - processed_frame_count
    target_frame_count = sum(1 for record in records if record.has_target)
    processed_target_frame_count = sum(
        1
        for record, processed in zip(records, processed_flags, strict=True)
        if record.has_target and processed
    )
    skipped_target_frame_count = target_frame_count - processed_target_frame_count
    target_gt_count = sum(record.target_gt_count for record in records)
    processed_target_gt_count = sum(
        record.target_gt_count
        for record, processed in zip(records, processed_flags, strict=True)
        if processed
    )
    skipped_target_gt_count = target_gt_count - processed_target_gt_count
    target_skip_runs = _skip_run_lengths(records, processed_flags, only_target=True)
    return TemporalGateProfileReport(
        profile=profile,
        frame_count=len(records),
        processed_frame_count=processed_frame_count,
        skipped_frame_count=skipped_frame_count,
        target_frame_count=target_frame_count,
        processed_target_frame_count=processed_target_frame_count,
        skipped_target_frame_count=skipped_target_frame_count,
        target_gt_count=target_gt_count,
        processed_target_gt_count=processed_target_gt_count,
        skipped_target_gt_count=skipped_target_gt_count,
        max_skip_run_frames=max(_skip_run_lengths(records, processed_flags), default=0),
        max_target_skip_run_frames=max(target_skip_runs, default=0),
        mean_target_skip_run_frames=_average(target_skip_runs),
    )


def write_temporal_gate_report_json(report: TemporalGateReport, output_path: str | Path) -> None:
    write_json(report.to_json_dict(), output_path)


def write_temporal_gate_report_markdown(report: TemporalGateReport, output_path: str | Path) -> None:
    write_text(report.to_markdown(), output_path)


def _should_process(
    record: TemporalFrameRecord,
    profile: TemporalGateProfile,
    last_processed_index: int | None,
) -> bool:
    if profile.mode == "all":
        return True
    if profile.mode == "fixed_interval":
        interval = max(1, profile.interval)
        return record.frame_index % interval == 0
    if profile.mode == "scene_delta":
        if last_processed_index is None:
            return True
        if record.scene_delta_mean >= profile.scene_delta_threshold:
            return True
        if profile.max_refresh_interval is None:
            return False
        return record.frame_index - last_processed_index >= profile.max_refresh_interval
    raise ValueError(f"Unsupported temporal gate mode: {profile.mode}")


def _skip_run_lengths(
    records: list[TemporalFrameRecord],
    processed_flags: list[bool],
    only_target: bool = False,
) -> list[int]:
    runs: list[int] = []
    current = 0
    for record, processed in zip(records, processed_flags, strict=True):
        if processed or (only_target and not record.has_target):
            if current:
                runs.append(current)
                current = 0
            continue
        current += 1
    if current:
        runs.append(current)
    return runs


def _average(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)
