"""Rule-based ROI generator orchestration."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from common import FramePacket, FrameSize, ROI, TriggerType
from roi_generator.budget import BudgetFallbackDecision, evaluate_budget_fallback, should_fallback_to_full_frame
from roi_generator.config import RoiGeneratorConfig, load_roi_generator_config
from roi_generator.contract import GateDecision
from roi_generator.signals.event_encoder import EventMaps, encode_event_maps
from roi_generator.policies import ComponentBboxPolicy, RoiPolicy
from roi_generator.signals.preprocess import resize_for_analysis, to_gray
from roi_generator.temporal_hold import TemporalHold
from roi_generator.trace import RoiDebugSink, RoiDebugSnapshot, RoiGenerationTrace


class RuleBasedRoiGenerator:
    """Converts FramePacket input into ROI or full-frame trigger decisions."""

    def __init__(
        self,
        config: RoiGeneratorConfig,
        debug_sink: RoiDebugSink | None = None,
        policy: RoiPolicy | None = None,
    ) -> None:
        self.config = config
        self.policy = policy or ComponentBboxPolicy(config)
        self.debug_sink = debug_sink
        self._temporal_hold = TemporalHold(config.hold_frames)
        self._previous_analysis_gray = None
        self._previous_analysis_size: FrameSize | None = None

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

        if self._previous_analysis_gray is None:
            self._remember_analysis_frame(analysis_gray, analysis_size)
            decision = self._full_frame_decision(
                packet=packet,
                rois=[],
                started=started,
                event_maps=None,
                analysis_size=analysis_size,
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
        current_rois = generation_trace.final_rois
        budget_fallback = evaluate_budget_fallback(current_rois, packet.original_size, self.config)
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
            )
            self._emit_debug_snapshot(
                packet=packet,
                analysis_gray=analysis_gray,
                previous_analysis_gray=previous_analysis_gray,
                event_maps=event_maps,
                generation_trace=generation_trace,
                decision=decision,
                budget_fallback=budget_fallback,
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
            )
            self._emit_debug_snapshot(
                packet=packet,
                analysis_gray=analysis_gray,
                previous_analysis_gray=previous_analysis_gray,
                event_maps=event_maps,
                generation_trace=generation_trace,
                decision=decision,
                budget_fallback=budget_fallback,
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
        )
        self._emit_debug_snapshot(
            packet=packet,
            analysis_gray=analysis_gray,
            previous_analysis_gray=previous_analysis_gray,
            event_maps=event_maps,
            generation_trace=generation_trace,
            decision=decision,
            budget_fallback=budget_fallback,
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
    ) -> GateDecision:
        return self._decision(
            packet=packet,
            trigger_type=TriggerType.FULL_FRAME,
            rois=rois,
            started=started,
            should_run_full_frame=True,
            event_maps=event_maps,
            analysis_size=analysis_size,
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
    ) -> GateDecision:
        if analysis_size is None:
            analysis_size = self.config.analysis_size_for_frame(packet.original_size)
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
            )
        )


def is_periodic_full_frame(frame_id: int, interval: int) -> bool:
    return interval > 0 and frame_id > 0 and frame_id % interval == 0


def sort_rois_by_area(rois: list[ROI]) -> list[ROI]:
    return sorted(rois, key=lambda roi: roi.area(), reverse=True)
