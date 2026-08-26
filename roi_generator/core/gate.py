"""Rule-based ROI generator orchestration."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from common import Detection, FramePacket, FrameSize, ROI, TriggerType
from roi_generator.core.budget import (
    BudgetFallbackDecision,
    estimate_budget_cost,
    evaluate_budget_fallback,
    should_fallback_to_full_frame,
)
from roi_generator.core.config import RoiGeneratorConfig, load_roi_generator_config
from roi_generator.core.contract import GateDecision
from roi_generator.core.decision_reasons import (
    ANALYSIS_SIZE_CHANGED,
    INITIAL_FRAME,
    PERIODIC_FULL_FRAME,
    REFERENCE_FEEDBACK,
    reason_for_trigger,
)
from roi_generator.core.feedback import ReferenceFeedbackCache, ReferenceFeedbackResult
from roi_generator.signals.event_encoder import EventMaps, encode_event_maps
from roi_generator.policies import RoiPolicy, create_roi_policy
from roi_generator.signals.preprocess import resize_for_analysis, to_gray
from roi_generator.core.temporal_hold import TemporalHold
from roi_generator.observability.trace import RoiDebugSink, RoiDebugSnapshot, RoiGenerationTrace


class RuleBasedRoiGenerator:
    """Converts FramePacket input into ROI or full-frame trigger decisions."""

    def __init__(
        self,
        config: RoiGeneratorConfig,
        debug_sink: RoiDebugSink | None = None,
        policy: RoiPolicy | None = None,
    ) -> None:
        self.config = config
        self.policy = policy or create_roi_policy(config)
        self.debug_sink = debug_sink
        self._temporal_hold = TemporalHold(config.hold_frames)
        self._previous_analysis_gray = None
        self._previous_analysis_size: FrameSize | None = None
        self.last_generation_trace: RoiGenerationTrace | None = None
        self._reference_feedback = ReferenceFeedbackCache()

    def update_reference_feedback(self, detections: list[Detection]) -> None:
        self._reference_feedback.update(detections, self.config)

    def process(self, packet: FramePacket) -> GateDecision:
        started = perf_counter()
        analysis_size = self.config.analysis_size_for_frame(packet.original_size)
        analysis_gray = resize_for_analysis(to_gray(packet.frame), analysis_size)
        previous_analysis_gray = self._previous_analysis_gray
        empty_trace = RoiGenerationTrace(
            filtered_motion_map=None,
            candidate_analysis_rois=[],
            merged_analysis_rois=[],
            final_rois=[],
        )
        self.last_generation_trace = empty_trace

        if self._previous_analysis_gray is None:
            self._remember_analysis_frame(analysis_gray, analysis_size)
            decision = self._full_frame_decision(
                packet=packet,
                rois=[],
                started=started,
                event_maps=None,
                analysis_size=analysis_size,
                decision_reason=INITIAL_FRAME,
            )
            self._emit_debug_snapshot(
                packet=packet,
                analysis_gray=analysis_gray,
                previous_analysis_gray=previous_analysis_gray,
                event_maps=None,
                generation_trace=empty_trace,
                decision=decision,
                budget_fallback=BudgetFallbackDecision(False),
            )
            return decision

        if self._previous_analysis_size != analysis_size:
            self._remember_analysis_frame(analysis_gray, analysis_size)
            self._temporal_hold.clear()
            decision = self._full_frame_decision(
                packet=packet,
                rois=[],
                started=started,
                event_maps=None,
                analysis_size=analysis_size,
                decision_reason=ANALYSIS_SIZE_CHANGED,
            )
            self._emit_debug_snapshot(
                packet=packet,
                analysis_gray=analysis_gray,
                previous_analysis_gray=previous_analysis_gray,
                event_maps=None,
                generation_trace=empty_trace,
                decision=decision,
                budget_fallback=BudgetFallbackDecision(False),
            )
            return decision

        event_maps = self._encode_event_maps(analysis_gray)
        self._remember_analysis_frame(analysis_gray, analysis_size)

        generation_trace = self._generate_roi_trace(event_maps, analysis_size, packet.original_size)
        self.last_generation_trace = generation_trace
        feedback_result = self._reference_feedback.candidates(
            camera_id=packet.camera_id,
            frame_id=packet.frame_id,
            frame_size=packet.original_size,
            config=self.config,
        )
        current_rois = merge_feedback_rois(
            generation_trace.final_rois,
            feedback_result,
            duplicate_overlap_ratio=self.config.reference_feedback_duplicate_overlap_ratio,
        )
        current_selected_tile_count = policy_selected_tile_count(generation_trace, self.policy.name)
        current_tile_group_count = tile_group_count(generation_trace, self.policy.name)
        budget_fallback = evaluate_budget_fallback(
            current_rois,
            packet.original_size,
            self.config,
            selected_tile_count=current_selected_tile_count,
            tile_group_count=current_tile_group_count,
            tile_budget_applies=tile_budget_applies(self.policy.name),
        )
        if budget_fallback.should_fallback:
            self._temporal_hold.clear()
            decision = self._decision(
                packet=packet,
                trigger_type=TriggerType.FALLBACK_FULL_FRAME,
                rois=[],
                started=started,
                should_run_full_frame=True,
                event_maps=event_maps,
                analysis_size=analysis_size,
                decision_reason=budget_fallback.reason or "budget_fallback",
                selected_tile_count=current_selected_tile_count,
                tile_group_count=current_tile_group_count,
                trace=generation_trace,
                feedback_result=feedback_result,
                feedback_assisted_roi_count=feedback_roi_count(feedback_result, current_rois),
            )
            self._emit_debug_snapshot(
                packet=packet,
                analysis_gray=analysis_gray,
                previous_analysis_gray=previous_analysis_gray,
                event_maps=event_maps,
                generation_trace=generation_trace,
                decision=decision,
                budget_fallback=budget_fallback,
                feedback_result=feedback_result,
            )
            return decision

        held_rois = self._temporal_hold.update(current_rois)
        trigger_type, rois = self._roi_or_hold_decision(current_rois, held_rois)

        if is_periodic_full_frame(packet.frame_id, self.config.full_frame_interval):
            decision = self._full_frame_decision(
                packet=packet,
                rois=rois,
                started=started,
                event_maps=event_maps,
                analysis_size=analysis_size,
                decision_reason=PERIODIC_FULL_FRAME,
                selected_tile_count=current_selected_tile_count,
                tile_group_count=current_tile_group_count,
                trace=generation_trace,
                feedback_result=feedback_result,
                feedback_assisted_roi_count=feedback_roi_count(feedback_result, rois),
            )
            self._emit_debug_snapshot(
                packet=packet,
                analysis_gray=analysis_gray,
                previous_analysis_gray=previous_analysis_gray,
                event_maps=event_maps,
                generation_trace=generation_trace,
                decision=decision,
                budget_fallback=budget_fallback,
                feedback_result=feedback_result,
            )
            return decision

        decision = self._decision(
            packet=packet,
            trigger_type=trigger_type,
            rois=rois,
            started=started,
            should_run_full_frame=False,
            event_maps=event_maps,
            analysis_size=analysis_size,
            decision_reason=decision_reason_for_rois(trigger_type, generation_trace.final_rois, rois),
            selected_tile_count=current_selected_tile_count,
            tile_group_count=current_tile_group_count,
            trace=generation_trace,
            feedback_result=feedback_result,
            feedback_assisted_roi_count=feedback_roi_count(feedback_result, rois),
        )
        self._emit_debug_snapshot(
            packet=packet,
            analysis_gray=analysis_gray,
            previous_analysis_gray=previous_analysis_gray,
            event_maps=event_maps,
            generation_trace=generation_trace,
            decision=decision,
            budget_fallback=budget_fallback,
            feedback_result=feedback_result,
        )
        return decision

    def _remember_analysis_frame(self, analysis_gray, analysis_size: FrameSize) -> None:
        self._previous_analysis_gray = analysis_gray
        self._previous_analysis_size = analysis_size

    def _encode_event_maps(self, analysis_gray) -> EventMaps:
        return encode_event_maps(
            current_gray=analysis_gray,
            previous_gray=self._previous_analysis_gray,
            threshold_on=self.config.threshold_on,
            threshold_off=self.config.threshold_off,
            threshold_motion=self.config.threshold_motion,
        )

    def _generate_roi_trace(
        self,
        event_maps: EventMaps,
        analysis_size: FrameSize,
        original_size: FrameSize,
    ) -> RoiGenerationTrace:
        return self.policy.generate(event_maps, analysis_size, original_size)

    def _roi_or_hold_decision(self, current_rois: list[ROI], held_rois: list[ROI]) -> tuple[TriggerType, list[ROI]]:
        if current_rois:
            return TriggerType.ROI, current_rois
        if held_rois:
            return TriggerType.HOLD, held_rois
        return TriggerType.NONE, []

    def _full_frame_decision(
        self,
        packet: FramePacket,
        rois: list[ROI],
        started: float,
        event_maps: EventMaps | None,
        analysis_size: FrameSize,
        decision_reason: str,
        selected_tile_count: int = 0,
        tile_group_count: int = 0,
        trace: RoiGenerationTrace | None = None,
        feedback_result: ReferenceFeedbackResult | None = None,
        feedback_assisted_roi_count: int = 0,
    ) -> GateDecision:
        return self._decision(
            packet=packet,
            trigger_type=TriggerType.FULL_FRAME,
            rois=rois,
            started=started,
            should_run_full_frame=True,
            event_maps=event_maps,
            analysis_size=analysis_size,
            decision_reason=decision_reason,
            selected_tile_count=selected_tile_count,
            tile_group_count=tile_group_count,
            trace=trace,
            feedback_result=feedback_result,
            feedback_assisted_roi_count=feedback_assisted_roi_count,
        )

    def _decision(
        self,
        packet: FramePacket,
        trigger_type: TriggerType,
        rois: list[ROI],
        started: float,
        should_run_full_frame: bool,
        event_maps: EventMaps | None,
        analysis_size: FrameSize | None = None,
        decision_reason: str | None = None,
        selected_tile_count: int = 0,
        tile_group_count: int = 0,
        trace: RoiGenerationTrace | None = None,
        feedback_result: ReferenceFeedbackResult | None = None,
        feedback_assisted_roi_count: int = 0,
    ) -> GateDecision:
        if analysis_size is None:
            analysis_size = self.config.analysis_size_for_frame(packet.original_size)
        budget_cost = estimate_budget_cost(
            rois=rois,
            frame_size=packet.original_size,
            selected_tile_count=selected_tile_count,
            tile_group_count=tile_group_count,
            should_run_full_frame=should_run_full_frame,
        )
        return GateDecision(
            camera_id=packet.camera_id,
            frame_id=packet.frame_id,
            timestamp=packet.timestamp,
            trigger_type=trigger_type,
            rois=rois,
            original_frame_size=packet.original_size,
            analysis_frame_size=analysis_size,
            gate_latency_ms=(perf_counter() - started) * 1000.0,
            should_run_full_frame=should_run_full_frame,
            policy_label=self.policy.name,
            decision_reason=decision_reason,
            roi_batch_slots_used=budget_cost.roi_batch_slots_used,
            tile_group_count=budget_cost.tile_group_count,
            selected_tile_count=budget_cost.selected_tile_count,
            estimated_tensor_pixels=budget_cost.estimated_tensor_pixels,
            tensor_batch_cost=budget_cost.tensor_batch_cost,
            effective_input_area=budget_cost.effective_input_area,
            raw_component_count=(trace.raw_component_count if trace else 0),
            filtered_component_count=(trace.filtered_component_count if trace else 0),
            merged_roi_count=(len(trace.merged_analysis_rois) if trace else 0),
            motion_density=(trace.motion_density if trace else 0.0),
            final_roi_area_ratio=final_roi_area_ratio(trace, packet.original_size) if trace else 0.0,
            feedback_candidate_count=(len(feedback_result.candidates) if feedback_result else 0),
            feedback_assisted_roi_count=feedback_assisted_roi_count,
            feedback_active_track_count=(feedback_result.active_track_count if feedback_result else 0),
            feedback_stale_track_count=(feedback_result.stale_track_count if feedback_result else 0),
            event_maps=event_maps,
        )

    def _emit_debug_snapshot(
        self,
        packet: FramePacket,
        analysis_gray: Any,
        previous_analysis_gray: Any | None,
        event_maps: EventMaps | None,
        generation_trace: RoiGenerationTrace,
        decision: GateDecision,
        budget_fallback: BudgetFallbackDecision,
        feedback_result: ReferenceFeedbackResult | None = None,
    ) -> None:
        if self.debug_sink is None:
            return
        self.debug_sink.write(
            RoiDebugSnapshot(
                packet=packet,
                config=self.config,
                analysis_gray=analysis_gray,
                previous_analysis_gray=previous_analysis_gray,
                event_maps=event_maps,
                generation_trace=generation_trace,
                decision=decision,
                budget_fallback=budget_fallback,
                feedback_rois=(
                    [candidate.roi for candidate in feedback_result.candidates]
                    if feedback_result is not None
                    else []
                ),
            )
        )


def is_periodic_full_frame(frame_id: int, interval: int) -> bool:
    return interval > 0 and frame_id > 0 and frame_id % interval == 0


def selected_tile_count(trace: RoiGenerationTrace) -> int:
    return sum(1 for tile in trace.tile_traces if tile.selected)


def policy_selected_tile_count(trace: RoiGenerationTrace, policy_label: str) -> int:
    if not tile_budget_applies(policy_label):
        return 0
    return selected_tile_count(trace)


def tile_group_count(trace: RoiGenerationTrace, policy_label: str) -> int:
    if not tile_budget_applies(policy_label):
        return 0
    if selected_tile_count(trace) == 0:
        return 0
    return len(trace.final_rois)


def tile_budget_applies(policy_label: str) -> bool:
    return policy_label in {"tile_mask", "hybrid_component_tile"}


def final_roi_area_ratio(trace: RoiGenerationTrace, frame_size: FrameSize) -> float:
    frame_area = frame_size.area()
    if frame_area <= 0:
        return 0.0
    return sum(roi.area() for roi in trace.final_rois) / frame_area


def merge_feedback_rois(
    policy_rois: list[ROI],
    feedback_result: ReferenceFeedbackResult,
    duplicate_overlap_ratio: float = 1.0,
) -> list[ROI]:
    merged = list(policy_rois)
    for candidate in feedback_result.candidates:
        if not any(roi_overlap_ratio(existing, candidate.roi) >= duplicate_overlap_ratio for existing in merged):
            merged.append(candidate.roi)
    return sort_rois_by_area(merged)


def feedback_roi_count(feedback_result: ReferenceFeedbackResult, decision_rois: list[ROI]) -> int:
    return sum(
        1
        for candidate in feedback_result.candidates
        if any(same_roi(candidate.roi, roi) for roi in decision_rois)
    )


def decision_reason_for_rois(trigger_type: TriggerType, policy_rois: list[ROI], decision_rois: list[ROI]) -> str:
    if trigger_type == TriggerType.ROI and not policy_rois and decision_rois:
        return REFERENCE_FEEDBACK
    return reason_for_trigger(trigger_type)


def roi_overlap_ratio(existing: ROI, candidate: ROI) -> float:
    candidate_area = candidate.area()
    if candidate_area <= 0:
        return 0.0
    x1 = max(existing.x, candidate.x)
    y1 = max(existing.y, candidate.y)
    x2 = min(existing.x + existing.w, candidate.x + candidate.w)
    y2 = min(existing.y + existing.h, candidate.y + candidate.h)
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    return intersection / candidate_area


def same_roi(left: ROI, right: ROI) -> bool:
    return left.xywh() == right.xywh() and left.coord_system == right.coord_system


def sort_rois_by_area(rois: list[ROI]) -> list[ROI]:
    return sorted(rois, key=lambda roi: roi.area(), reverse=True)
