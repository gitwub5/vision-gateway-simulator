from __future__ import annotations

import unittest
from unittest.mock import patch

from common import FramePacket, FrameSize, ROI, TriggerType
from roi_generator.gate import (
    RoiGeneratorConfig,
    RuleBasedRoiGenerator,
    evaluate_budget_fallback,
    is_periodic_full_frame,
    should_fallback_to_full_frame,
)
from roi_generator.temporal_hold import TemporalHold


class FakeGrayFrame:
    pass


class FakeEventMaps:
    motion_map = object()


class RuleBasedRoiGeneratorTest(unittest.TestCase):
    def test_processing_width_preserves_source_aspect_ratio(self) -> None:
        config = RoiGeneratorConfig(processing_width=1280)

        self.assertEqual(config.analysis_size_for_frame(FrameSize(width=3840, height=2160)), FrameSize(1280, 720))

    def test_processing_size_does_not_upscale_by_default(self) -> None:
        config = RoiGeneratorConfig(processing_width=1280)

        self.assertEqual(config.analysis_size_for_frame(FrameSize(width=640, height=360)), FrameSize(640, 360))

    def test_config_loads_nested_processing_size(self) -> None:
        config = RoiGeneratorConfig.from_mapping({"roi_generator": {"processing": {"width": 960}}})

        self.assertEqual(config.processing_width, 960)
        self.assertIsNone(config.processing_height)

    def test_config_loads_debug_options(self) -> None:
        config = RoiGeneratorConfig.from_mapping(
            {"roi_generator": {"debug": {"enabled": True, "max_frames": 120, "stride": 5}}}
        )

        self.assertTrue(config.debug_enabled)
        self.assertEqual(config.debug_max_frames, 120)
        self.assertEqual(config.debug_stride, 5)

    def test_decision_records_dynamic_analysis_size(self) -> None:
        gate = RuleBasedRoiGenerator(RoiGeneratorConfig(processing_width=1280, full_frame_interval=60))
        packet = _packet(frame_id=0, original_size=FrameSize(width=3840, height=2160))
        seen_sizes: list[FrameSize] = []

        with _patched_gate_helpers(rois=[], seen_sizes=seen_sizes):
            decision = gate.process(packet)

        self.assertEqual(seen_sizes, [FrameSize(width=1280, height=720)])
        self.assertEqual(decision.analysis_frame_size, FrameSize(width=1280, height=720))

    def test_first_frame_triggers_full_frame_check(self) -> None:
        gate = RuleBasedRoiGenerator(RoiGeneratorConfig(full_frame_interval=60))
        packet = _packet(frame_id=0)

        with _patched_gate_helpers(rois=[]):
            decision = gate.process(packet)

        self.assertEqual(decision.trigger_type, TriggerType.FULL_FRAME)
        self.assertTrue(decision.should_run_full_frame)
        self.assertEqual(decision.rois, [])

    def test_motion_roi_triggers_roi_decision(self) -> None:
        gate = RuleBasedRoiGenerator(RoiGeneratorConfig(full_frame_interval=60))

        with _patched_gate_helpers(rois=[ROI(x=10, y=10, w=20, h=20, coord_system="analysis_frame")]):
            gate.process(_packet(frame_id=0))
            decision = gate.process(_packet(frame_id=1))

        self.assertEqual(decision.trigger_type, TriggerType.ROI)
        self.assertFalse(decision.should_run_full_frame)
        self.assertEqual(len(decision.rois), 1)
        self.assertEqual(decision.rois[0].coord_system, "original_frame")
        self.assertGreater(decision.rois[0].w, 0)
        self.assertGreater(decision.rois[0].h, 0)

    def test_temporal_hold_triggers_when_motion_disappears(self) -> None:
        gate = RuleBasedRoiGenerator(RoiGeneratorConfig(hold_frames=2, full_frame_interval=60))

        with _patched_gate_helpers(rois=[ROI(x=10, y=10, w=20, h=20, coord_system="analysis_frame")]):
            gate.process(_packet(frame_id=0))
            first_motion = gate.process(_packet(frame_id=1))

        with _patched_gate_helpers(rois=[]):
            held = gate.process(_packet(frame_id=2))

        self.assertEqual(first_motion.trigger_type, TriggerType.ROI)
        self.assertEqual(held.trigger_type, TriggerType.HOLD)
        self.assertEqual(len(held.rois), 1)

    def test_periodic_full_frame_preserves_rois(self) -> None:
        gate = RuleBasedRoiGenerator(RoiGeneratorConfig(full_frame_interval=2))

        with _patched_gate_helpers(rois=[ROI(x=5, y=5, w=8, h=8, coord_system="analysis_frame")]):
            gate.process(_packet(frame_id=0))
            gate.process(_packet(frame_id=1))
            decision = gate.process(_packet(frame_id=2))

        self.assertEqual(decision.trigger_type, TriggerType.FULL_FRAME)
        self.assertTrue(decision.should_run_full_frame)
        self.assertEqual(len(decision.rois), 1)

    def test_excessive_roi_area_falls_back_to_full_frame(self) -> None:
        gate = RuleBasedRoiGenerator(
            RoiGeneratorConfig(full_frame_interval=60, max_total_roi_area_ratio=0.1, margin_ratio=0.0)
        )

        with _patched_gate_helpers(rois=[ROI(x=0, y=0, w=80, h=80, coord_system="analysis_frame")]):
            gate.process(_packet(frame_id=0))
            decision = gate.process(_packet(frame_id=1))

        self.assertEqual(decision.trigger_type, TriggerType.FALLBACK_FULL_FRAME)
        self.assertTrue(decision.should_run_full_frame)
        self.assertEqual(decision.rois, [])

    def test_debug_sink_receives_per_frame_generation_trace(self) -> None:
        sink = FakeDebugSink()
        gate = RuleBasedRoiGenerator(RoiGeneratorConfig(full_frame_interval=60), debug_sink=sink)

        with _patched_gate_helpers(rois=[ROI(x=10, y=10, w=20, h=20, coord_system="analysis_frame")]):
            gate.process(_packet(frame_id=0))
            decision = gate.process(_packet(frame_id=1))

        self.assertEqual(len(sink.snapshots), 2)
        self.assertEqual(sink.snapshots[0].decision.trigger_type, TriggerType.FULL_FRAME)
        self.assertEqual(sink.snapshots[1].decision, decision)
        self.assertEqual(len(sink.snapshots[1].generation_trace.candidate_analysis_rois), 1)
        self.assertEqual(len(sink.snapshots[1].generation_trace.final_rois), 1)


class GatePolicyTest(unittest.TestCase):
    def test_should_fallback_when_roi_count_exceeds_limit(self) -> None:
        config = RoiGeneratorConfig(max_roi_per_frame=1)
        rois = [ROI(0, 0, 10, 10), ROI(20, 20, 10, 10)]
        self.assertTrue(should_fallback_to_full_frame(rois, FrameSize(100, 100), config))
        self.assertEqual(evaluate_budget_fallback(rois, FrameSize(100, 100), config).reason, "max_roi_per_frame")

    def test_should_fallback_when_roi_area_exceeds_limit(self) -> None:
        config = RoiGeneratorConfig(max_total_roi_area_ratio=0.25)
        rois = [ROI(0, 0, 60, 60)]
        self.assertTrue(should_fallback_to_full_frame(rois, FrameSize(100, 100), config))
        self.assertEqual(evaluate_budget_fallback(rois, FrameSize(100, 100), config).reason, "max_total_roi_area_ratio")

    def test_periodic_full_frame_skips_first_frame_policy(self) -> None:
        self.assertFalse(is_periodic_full_frame(frame_id=0, interval=30))
        self.assertFalse(is_periodic_full_frame(frame_id=29, interval=30))
        self.assertTrue(is_periodic_full_frame(frame_id=30, interval=30))

    def test_temporal_hold_expires(self) -> None:
        hold = TemporalHold(hold_frames=2)
        roi = ROI(1, 2, 3, 4)

        self.assertEqual(hold.update([roi]), [roi])
        self.assertEqual(hold.update([]), [roi])
        self.assertEqual(hold.update([]), [])


class FakeDebugSink:
    def __init__(self) -> None:
        self.snapshots = []

    def write(self, snapshot) -> None:
        self.snapshots.append(snapshot)


def _packet(frame_id: int, original_size: FrameSize | None = None) -> FramePacket:
    if original_size is None:
        original_size = FrameSize(width=100, height=100)
    return FramePacket(
        camera_id="cam_test",
        frame_id=frame_id,
        timestamp=float(frame_id) / 30.0,
        frame=object(),
        original_size=original_size,
    )


def _patched_gate_helpers(rois: list[ROI], seen_sizes: list[FrameSize] | None = None):
    def resize(gray, analysis_size):
        if seen_sizes is not None:
            seen_sizes.append(analysis_size)
        return FakeGrayFrame()

    return patch.multiple(
        "roi_generator.gate",
        to_gray=lambda frame: FakeGrayFrame(),
        resize_for_analysis=resize,
        encode_event_maps=lambda **kwargs: FakeEventMaps(),
        filter_motion_map=lambda motion_map, kernel_size: motion_map,
        generate_roi_candidates=lambda motion_map, min_area_ratio: rois,
    )


if __name__ == "__main__":
    unittest.main()
