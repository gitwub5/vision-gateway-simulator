"""Hybrid ROI gate candidate selection from Phase 1.3 POC summaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common.io import read_json, write_json, write_text


@dataclass(frozen=True)
class SourceProfileSignal:
    family: str
    profile_name: str
    primary_recall: float
    input_reduction: float
    role: str
    notes: tuple[str, ...] = ()

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DomainHybridRecommendation:
    experiment_name: str
    selected_candidate: str
    confidence: str
    selection_reason: str
    source_profiles: tuple[SourceProfileSignal, ...] = ()
    rejected_candidates: tuple[str, ...] = ()

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_profiles"] = [profile.to_json_dict() for profile in self.source_profiles]
        data["rejected_candidates"] = list(self.rejected_candidates)
        return data


@dataclass(frozen=True)
class HybridCandidateFamily:
    name: str
    status: str
    target_domains: tuple[str, ...]
    rationale: str
    required_next_probe: str

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HybridGateSelectionReport:
    static_summary_path: str
    tracker_summary_path: str
    lightweight_summary_path: str
    temporal_summary_path: str
    compression_summary_path: str | None
    recommendations: dict[str, DomainHybridRecommendation] = field(default_factory=dict)
    candidate_families: tuple[HybridCandidateFamily, ...] = ()

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "static_summary_path": self.static_summary_path,
            "tracker_summary_path": self.tracker_summary_path,
            "lightweight_summary_path": self.lightweight_summary_path,
            "temporal_summary_path": self.temporal_summary_path,
            "compression_summary_path": self.compression_summary_path,
            "candidate_families": [family.to_json_dict() for family in self.candidate_families],
            "recommendations": {
                name: recommendation.to_json_dict()
                for name, recommendation in self.recommendations.items()
            },
        }

    def to_markdown(self) -> str:
        lines = [
            "# Phase 1.3-G Hybrid Gate Candidate Selection",
            "",
            "## Candidate Families",
            "",
            "| Candidate | Status | Target domains | Required next probe |",
            "| --- | --- | --- | --- |",
        ]
        for family in self.candidate_families:
            lines.append(
                "| "
                f"`{family.name}` | "
                f"`{family.status}` | "
                f"{', '.join(family.target_domains)} | "
                f"{family.required_next_probe} |"
            )
        lines.extend(["", "## Domain Recommendations", ""])
        lines.append("| Dataset | Selected candidate | Confidence | Reason |")
        lines.append("| --- | --- | --- | --- |")
        for recommendation in self.recommendations.values():
            lines.append(
                "| "
                f"`{recommendation.experiment_name}` | "
                f"`{recommendation.selected_candidate}` | "
                f"`{recommendation.confidence}` | "
                f"{recommendation.selection_reason} |"
            )
        lines.extend(["", "## Source Profiles", ""])
        for recommendation in self.recommendations.values():
            lines.append(f"### `{recommendation.experiment_name}`")
            lines.append("")
            lines.append("| Family | Profile | Role | Primary recall | Input reduction | Notes |")
            lines.append("| --- | --- | --- | ---: | ---: | --- |")
            for profile in recommendation.source_profiles:
                notes = "; ".join(profile.notes)
                lines.append(
                    "| "
                    f"`{profile.family}` | "
                    f"`{profile.profile_name}` | "
                    f"{profile.role} | "
                    f"{profile.primary_recall:.3f} | "
                    f"{profile.input_reduction:.3f} | "
                    f"{notes} |"
                )
            if recommendation.rejected_candidates:
                lines.append("")
                lines.append(f"Rejected: {', '.join(f'`{name}`' for name in recommendation.rejected_candidates)}")
            lines.append("")
        return "\n".join(lines)


def build_hybrid_gate_selection_report(
    static_summary_path: str | Path,
    tracker_summary_path: str | Path,
    lightweight_summary_path: str | Path,
    temporal_summary_path: str | Path,
    compression_summary_path: str | Path | None = None,
) -> HybridGateSelectionReport:
    static_runs = _runs_by_name(read_json(static_summary_path))
    tracker_runs = _runs_by_name(read_json(tracker_summary_path))
    lightweight_runs = _runs_by_name(read_json(lightweight_summary_path))
    temporal_runs = _runs_by_name(read_json(temporal_summary_path))

    recommendations: dict[str, DomainHybridRecommendation] = {}
    for experiment_name in static_runs:
        static_signal = _select_static_signal(static_runs[experiment_name])
        tracker_signal = _select_tracker_signal(tracker_runs[experiment_name])
        lightweight_signal = _select_lightweight_signal(lightweight_runs[experiment_name])
        temporal_signal = _select_temporal_signal(temporal_runs[experiment_name])
        recommendations[experiment_name] = _recommend_for_domain(
            experiment_name=experiment_name,
            static_signal=static_signal,
            tracker_signal=tracker_signal,
            lightweight_signal=lightweight_signal,
            temporal_signal=temporal_signal,
        )

    return HybridGateSelectionReport(
        static_summary_path=str(static_summary_path),
        tracker_summary_path=str(tracker_summary_path),
        lightweight_summary_path=str(lightweight_summary_path),
        temporal_summary_path=str(temporal_summary_path),
        compression_summary_path=str(compression_summary_path) if compression_summary_path else None,
        recommendations=recommendations,
        candidate_families=_candidate_families(recommendations),
    )


def write_hybrid_gate_selection_report_json(report: HybridGateSelectionReport, output_path: str | Path) -> None:
    write_json(report.to_json_dict(), output_path)


def write_hybrid_gate_selection_report_markdown(report: HybridGateSelectionReport, output_path: str | Path) -> None:
    write_text(report.to_markdown(), output_path)


def _runs_by_name(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(run["experiment_name"]): run for run in summary.get("runs", [])}


def _select_static_signal(run: dict[str, Any]) -> SourceProfileSignal:
    profile_name, profile = max(
        run["profiles"].items(),
        key=lambda item: (
            item[1]["bbox_gt_recall"],
            item[1]["center_gt_recall"],
            item[1]["input_area_reduction"],
        ),
    )
    notes = [
        f"center_recall={profile['center_gt_recall']:.3f}",
        f"bbox_recall={profile['bbox_gt_recall']:.3f}",
    ]
    if profile["center_gt_recall"] >= 0.95:
        notes.append("strong spatial anchor")
    if profile["bbox_gt_recall"] < 0.90:
        notes.append("needs margin/shape expansion for detector handoff")
    return SourceProfileSignal(
        family="static_zone_prior",
        profile_name=profile_name,
        primary_recall=float(profile["bbox_gt_recall"]),
        input_reduction=float(profile["input_area_reduction"]),
        role="spatial anchor",
        notes=tuple(notes),
    )


def _select_tracker_signal(run: dict[str, Any]) -> SourceProfileSignal:
    viable = [
        item for item in run["profiles"].items()
        if item[1]["target_gt_recall"] >= 0.95
    ]
    if viable:
        profile_name, profile = max(viable, key=lambda item: item[1]["effective_input_area_reduction"])
    else:
        profile_name, profile = max(
            run["profiles"].items(),
            key=lambda item: (item[1]["target_gt_recall"], item[1]["effective_input_area_reduction"]),
        )
    notes = [
        f"memory_recall={profile['memory_frame_target_gt_recall']:.3f}",
        f"roi_per_memory_frame={profile['average_memory_roi_count_per_memory_frame']:.1f}",
    ]
    if profile["target_gt_recall"] >= 0.95:
        notes.append("viable detector-refresh candidate")
    elif profile["target_gt_recall"] < 0.85:
        notes.append("simple hold-memory is too weak")
    if profile["average_memory_roi_count_per_memory_frame"] > 20:
        notes.append("ROI count budget risk")
    return SourceProfileSignal(
        family="tracker_memory",
        profile_name=profile_name,
        primary_recall=float(profile["target_gt_recall"]),
        input_reduction=float(profile["effective_input_area_reduction"]),
        role="short-term persistence",
        notes=tuple(notes),
    )


def _select_lightweight_signal(run: dict[str, Any]) -> SourceProfileSignal:
    profile_name, profile = max(
        run["profiles"].items(),
        key=lambda item: (
            item[1]["bbox_gt_recall"],
            item[1]["center_gt_recall"],
            item[1]["input_area_reduction"],
        ),
    )
    notes = [
        f"center_recall={profile['center_gt_recall']:.3f}",
        f"bbox_recall={profile['bbox_gt_recall']:.3f}",
    ]
    if profile["bbox_gt_recall"] >= 0.45:
        notes.append("usable as secondary busy-region score")
    else:
        notes.append("too weak as detector ROI")
    return SourceProfileSignal(
        family="lightweight_visual_signal",
        profile_name=profile_name,
        primary_recall=float(profile["bbox_gt_recall"]),
        input_reduction=float(profile["input_area_reduction"]),
        role="secondary prioritization",
        notes=tuple(notes),
    )


def _select_temporal_signal(run: dict[str, Any]) -> SourceProfileSignal:
    viable = [
        item for item in run["profiles"].items()
        if item[0] != "process_all" and item[1]["target_gt_recall"] >= 0.90
    ]
    if viable:
        profile_name, profile = max(viable, key=lambda item: item[1]["detector_call_reduction"])
    else:
        profile_name, profile = "process_all", run["profiles"]["process_all"]
    notes = [
        f"target_frame_recall={profile['target_frame_recall']:.3f}",
        f"detector_call_reduction={profile['detector_call_reduction']:.3f}",
    ]
    if profile_name == "process_all":
        notes.append("no safe standalone skip profile found")
    return SourceProfileSignal(
        family="temporal_gate",
        profile_name=profile_name,
        primary_recall=float(profile["target_gt_recall"]),
        input_reduction=float(profile["detector_call_reduction"]),
        role="refresh cadence guard",
        notes=tuple(notes),
    )


def _recommend_for_domain(
    experiment_name: str,
    static_signal: SourceProfileSignal,
    tracker_signal: SourceProfileSignal,
    lightweight_signal: SourceProfileSignal,
    temporal_signal: SourceProfileSignal,
) -> DomainHybridRecommendation:
    source_profiles = (static_signal, tracker_signal, lightweight_signal, temporal_signal)
    rejected = ["compression_signal"]

    if "traffic" in experiment_name:
        return DomainHybridRecommendation(
            experiment_name=experiment_name,
            selected_candidate="lane_or_scale_prior + velocity_tracker",
            confidence="needs_new_probe",
            selection_reason=(
                "static center prior is strong, but bbox containment and simple tracker recall are weak; "
                "traffic needs lane/scale-aware expansion and velocity prediction instead of current hold-memory."
            ),
            source_profiles=source_profiles,
            rejected_candidates=tuple(rejected + ["static_tracker_memory", "static_lightweight_priority"]),
        )
    if tracker_signal.primary_recall >= 0.95 and tracker_signal.input_reduction >= 0.60:
        return DomainHybridRecommendation(
            experiment_name=experiment_name,
            selected_candidate="static_zone_prior + tracker_memory + temporal_refresh_guard",
            confidence="high",
            selection_reason=(
                "tracker memory preserves high recall while reducing effective input; static prior can seed "
                "camera-specific regions and temporal gate should only bound refresh cadence."
            ),
            source_profiles=source_profiles,
            rejected_candidates=tuple(rejected),
        )
    if static_signal.primary_recall >= 0.90 and lightweight_signal.primary_recall >= 0.45:
        return DomainHybridRecommendation(
            experiment_name=experiment_name,
            selected_candidate="static_zone_prior + lightweight_visual_priority",
            confidence="medium",
            selection_reason=(
                "static prior already covers most bbox targets, while lightweight signal is useful as a "
                "busy-region priority score under ROI budget pressure."
            ),
            source_profiles=source_profiles,
            rejected_candidates=tuple(rejected + ["tracker_memory_primary"]),
        )
    if tracker_signal.primary_recall >= 0.95:
        return DomainHybridRecommendation(
            experiment_name=experiment_name,
            selected_candidate="tracker_memory + ROI_budget_cap",
            confidence="medium",
            selection_reason=(
                "tracker recall is high, but ROI count or scene instability requires a budget/packing layer "
                "before implementation."
            ),
            source_profiles=source_profiles,
            rejected_candidates=tuple(rejected),
        )
    return DomainHybridRecommendation(
        experiment_name=experiment_name,
        selected_candidate="static_zone_prior + lightweight_visual_priority",
        confidence="low",
        selection_reason=(
            "no current candidate is strong enough as a primary gate; keep static prior as anchor and use "
            "lightweight visual score only as a secondary prioritizer."
        ),
        source_profiles=source_profiles,
        rejected_candidates=tuple(rejected + ["tracker_memory_primary"]),
    )


def _candidate_families(
    recommendations: dict[str, DomainHybridRecommendation],
) -> tuple[HybridCandidateFamily, ...]:
    domains_by_candidate: dict[str, list[str]] = {}
    confidence_by_candidate: dict[str, list[str]] = {}
    for recommendation in recommendations.values():
        domains_by_candidate.setdefault(recommendation.selected_candidate, []).append(recommendation.experiment_name)
        confidence_by_candidate.setdefault(recommendation.selected_candidate, []).append(recommendation.confidence)

    families = [
        HybridCandidateFamily(
            name="static_zone_prior + tracker_memory + temporal_refresh_guard",
            status=_family_status(confidence_by_candidate.get("static_zone_prior + tracker_memory + temporal_refresh_guard", [])),
            target_domains=tuple(domains_by_candidate.get("static_zone_prior + tracker_memory + temporal_refresh_guard", [])),
            rationale="best current path when detector-refresh memory keeps recall high and input area low",
            required_next_probe="600-frame validation with non-oracle detector refresh, ROI packing, and stale-track handling",
        ),
        HybridCandidateFamily(
            name="static_zone_prior + lightweight_visual_priority",
            status=_family_status(confidence_by_candidate.get("static_zone_prior + lightweight_visual_priority", [])),
            target_domains=tuple(domains_by_candidate.get("static_zone_prior + lightweight_visual_priority", [])),
            rationale="keeps static prior as the spatial anchor and uses cheap visual signal only for budget ordering",
            required_next_probe="budgeted tile/ROI priority simulation and bbox-safe dilation sweep",
        ),
        HybridCandidateFamily(
            name="lane_or_scale_prior + velocity_tracker",
            status=_family_status(confidence_by_candidate.get("lane_or_scale_prior + velocity_tracker", [])),
            target_domains=tuple(domains_by_candidate.get("lane_or_scale_prior + velocity_tracker", [])),
            rationale="traffic needs motion direction and scale-aware prediction beyond simple bbox hold-memory",
            required_next_probe="new traffic-specific velocity/Kalman or lane-prior probe",
        ),
        HybridCandidateFamily(
            name="compression_signal",
            status="deferred",
            target_domains=(),
            rationale="current official datasets mostly lack encoded stream metadata",
            required_next_probe="encoded RTSP/video metadata extraction through ffprobe, GStreamer, or DeepStream",
        ),
    ]
    return tuple(families)


def _family_status(confidences: list[str]) -> str:
    if "high" in confidences:
        return "shortlist"
    if "medium" in confidences:
        return "secondary"
    if "low" in confidences:
        return "fallback_only"
    if "needs_new_probe" in confidences:
        return "needs_new_probe"
    return "not_selected"
