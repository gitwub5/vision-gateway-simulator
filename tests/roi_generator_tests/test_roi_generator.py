from __future__ import annotations

import unittest
from unittest.mock import patch

from common import Detection, FramePacket, FrameSize, ROI, TriggerType
from roi_generator.core.gate import (
    RoiGeneratorConfig,
    RuleBasedRoiGenerator,
    evaluate_budget_fallback,
    is_periodic_full_frame,
    should_fallback_to_full_frame,
)
from roi_generator.core.temporal_hold import TemporalHold


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

    def test_config_loads_tile_metadata_options(self) -> None:
        config = RoiGeneratorConfig.from_mapping(
            {
                "roi_generator": {
                    "tile_metadata": {
                        "grid_rows": 4,
                        "grid_cols": 6,
                        "motion_density_threshold": 0.2,
                    }
                }
            }
        )

        self.assertEqual(config.tile_grid_rows, 4)
        self.assertEqual(config.tile_grid_cols, 6)
        self.assertEqual(config.tile_motion_density_threshold, 0.2)

    def test_config_loads_adaptive_tile_threshold_options(self) -> None:
        config = RoiGeneratorConfig.from_mapping(
            {
                "roi_generator": {
                    "adaptive_tile_threshold": {
                        "enabled": True,
                        "ema_alpha": 0.25,
                        "multiplier": 2.0,
                        "additive_margin": 0.01,
                        "max_threshold": 0.2,
                        "warmup_frames": 3,
                    }
                }
            }
        )

        self.assertTrue(config.adaptive_tile_threshold_enabled)
        self.assertEqual(config.adaptive_tile_threshold_ema_alpha, 0.25)
        self.assertEqual(config.adaptive_tile_threshold_multiplier, 2.0)
        self.assertEqual(config.adaptive_tile_threshold_additive_margin, 0.01)
        self.assertEqual(config.adaptive_tile_threshold_max_threshold, 0.2)
        self.assertEqual(config.adaptive_tile_threshold_warmup_frames, 3)

    def test_config_loads_rare_tile_guard_options(self) -> None:
        config = RoiGeneratorConfig.from_mapping(
            {
                "roi_generator": {
                    "rare_tile_guard": {
                        "enabled": True,
                        "min_history_frames": 10,
                        "max_activation_rate": 0.2,
                        "weak_density_max": 0.03,
                    }
                }
            }
        )

        self.assertTrue(config.rare_tile_guard_enabled)
        self.assertEqual(config.rare_tile_guard_min_history_frames, 10)
        self.assertEqual(config.rare_tile_guard_max_activation_rate, 0.2)
        self.assertEqual(config.rare_tile_guard_weak_density_max, 0.03)

    def test_config_loads_nested_budget_options(self) -> None:
        config = RoiGeneratorConfig.from_mapping(
            {
                "roi_generator": {
                    "budget": {
                        "enabled": False,
                        "max_roi_per_frame": 3,
                        "max_total_roi_area_ratio": 0.4,
                        "max_selected_tile_count": 12,
                        "max_tensor_batch_cost": 12345,
                    }
                }
            }
        )

        self.assertFalse(config.budget_enabled)
        self.assertEqual(config.max_roi_per_frame, 3)
        self.assertEqual(config.max_total_roi_area_ratio, 0.4)
        self.assertEqual(config.max_selected_tile_count, 12)
        self.assertEqual(config.max_tensor_batch_cost, 12345)

    def test_config_loads_small_object_boost_options(self) -> None:
        config = RoiGeneratorConfig.from_mapping(
            {
                "roi_generator": {
                    "small_object_boost": {
                        "enabled": True,
                        "tile_overlap_ratio": 0.5,
                    }
                }
            }
        )

        self.assertTrue(config.small_object_boost_enabled)
        self.assertEqual(config.tile_overlap_ratio, 0.5)

    def test_config_loads_reference_feedback_options(self) -> None:
        config = RoiGeneratorConfig.from_mapping(
            {
                "roi_generator": {
                    "reference_feedback": {
                        "enabled": True,
                        "ttl_frames": 12,
                        "min_confidence": 0.4,
                        "margin_ratio": 0.1,
                        "max_candidates_per_frame": 2,
                        "duplicate_overlap_ratio": 0.6,
                    }
                }
            }
        )

        self.assertTrue(config.reference_feedback_enabled)
        self.assertEqual(config.reference_feedback_ttl_frames, 12)
        self.assertEqual(config.reference_feedback_min_confidence, 0.4)
        self.assertEqual(config.reference_feedback_margin_ratio, 0.1)
        self.assertEqual(config.reference_feedback_max_candidates_per_frame, 2)
        self.assertEqual(config.reference_feedback_duplicate_overlap_ratio, 0.6)

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
        gate = RuleBasedRoiGenerator(
            RoiGeneratorConfig(full_frame_interval=60),
            policy=FakePolicy([ROI(x=10, y=10, w=20, h=20, coord_system="analysis_frame")]),
        )

        with _patched_gate_helpers():
            gate.process(_packet(frame_id=0))
            decision = gate.process(_packet(frame_id=1))

        self.assertEqual(decision.trigger_type, TriggerType.ROI)
        self.assertFalse(decision.should_run_full_frame)
        self.assertEqual(len(decision.rois), 1)
        self.assertEqual(decision.rois[0].coord_system, "original_frame")
        self.assertGreater(decision.rois[0].w, 0)
        self.assertGreater(decision.rois[0].h, 0)
        self.assertEqual(decision.policy_label, "fake_policy")
        self.assertEqual(decision.decision_reason, "roi_selected")
        self.assertEqual(decision.roi_batch_slots_used, 1)
        self.assertEqual(decision.estimated_tensor_pixels, 400)
        self.assertEqual(decision.tensor_batch_cost, 400)
        self.assertEqual(decision.effective_input_area, 400)

    def test_temporal_hold_triggers_when_motion_disappears(self) -> None:
        gate = RuleBasedRoiGenerator(
            RoiGeneratorConfig(hold_frames=2, full_frame_interval=60),
            policy=FakePolicy([ROI(x=10, y=10, w=20, h=20, coord_system="analysis_frame")]),
        )

        with _patched_gate_helpers():
            gate.process(_packet(frame_id=0))
            first_motion = gate.process(_packet(frame_id=1))

        gate.policy = FakePolicy([])
        with _patched_gate_helpers():
            held = gate.process(_packet(frame_id=2))

        self.assertEqual(first_motion.trigger_type, TriggerType.ROI)
        self.assertEqual(held.trigger_type, TriggerType.HOLD)
        self.assertEqual(len(held.rois), 1)

    def test_periodic_full_frame_preserves_rois(self) -> None:
        gate = RuleBasedRoiGenerator(
            RoiGeneratorConfig(full_frame_interval=2),
            policy=FakePolicy([ROI(x=5, y=5, w=8, h=8, coord_system="analysis_frame")]),
        )

        with _patched_gate_helpers():
            gate.process(_packet(frame_id=0))
            gate.process(_packet(frame_id=1))
            decision = gate.process(_packet(frame_id=2))

        self.assertEqual(decision.trigger_type, TriggerType.FULL_FRAME)
        self.assertTrue(decision.should_run_full_frame)
        self.assertEqual(len(decision.rois), 1)

    def test_excessive_roi_area_falls_back_to_full_frame(self) -> None:
        gate = RuleBasedRoiGenerator(
            RoiGeneratorConfig(full_frame_interval=60, max_total_roi_area_ratio=0.1, margin_ratio=0.0),
            policy=FakePolicy([ROI(x=0, y=0, w=80, h=80, coord_system="analysis_frame")]),
        )

        with _patched_gate_helpers():
            gate.process(_packet(frame_id=0))
            decision = gate.process(_packet(frame_id=1))

        self.assertEqual(decision.trigger_type, TriggerType.FALLBACK_FULL_FRAME)
        self.assertTrue(decision.should_run_full_frame)
        self.assertEqual(decision.rois, [])
        self.assertEqual(decision.decision_reason, "roi_area_near_full_frame")
        self.assertEqual(decision.effective_input_area, 10000)

    def test_tile_budget_fallback_applies_to_tile_policy(self) -> None:
        gate = RuleBasedRoiGenerator(
            RoiGeneratorConfig(full_frame_interval=60, max_selected_tile_count=1),
            policy=FakePolicy(
                [ROI(x=0, y=0, w=10, h=10, coord_system="analysis_frame")],
                name="tile_mask",
                selected_tile_count=2,
            ),
        )

        with _patched_gate_helpers():
            gate.process(_packet(frame_id=0))
            decision = gate.process(_packet(frame_id=1))

        self.assertEqual(decision.trigger_type, TriggerType.FALLBACK_FULL_FRAME)
        self.assertEqual(decision.decision_reason, "tile_count_overhead_exceeds_gain")
        self.assertEqual(decision.selected_tile_count, 2)
        self.assertEqual(decision.tile_group_count, 1)

    def test_tile_budget_does_not_apply_to_component_policy_metadata(self) -> None:
        gate = RuleBasedRoiGenerator(
            RoiGeneratorConfig(full_frame_interval=60, max_selected_tile_count=1),
            policy=FakePolicy(
                [ROI(x=0, y=0, w=10, h=10, coord_system="analysis_frame")],
                name="component_bbox",
                selected_tile_count=2,
            ),
        )

        with _patched_gate_helpers():
            gate.process(_packet(frame_id=0))
            decision = gate.process(_packet(frame_id=1))

        self.assertEqual(decision.trigger_type, TriggerType.ROI)
        self.assertEqual(decision.decision_reason, "roi_selected")
        self.assertEqual(decision.selected_tile_count, 0)
        self.assertEqual(decision.tile_group_count, 0)

    def test_reference_feedback_can_create_roi_when_motion_policy_is_empty(self) -> None:
        gate = RuleBasedRoiGenerator(
            RoiGeneratorConfig(
                full_frame_interval=60,
                reference_feedback_enabled=True,
                reference_feedback_ttl_frames=5,
                reference_feedback_margin_ratio=0.0,
            ),
            policy=FakePolicy([]),
        )

        with _patched_gate_helpers():
            gate.process(_packet(frame_id=0))
            gate.update_reference_feedback([
                Detection(
                    camera_id="cam_test",
                    frame_id=0,
                    class_id=0,
                    class_name="person",
                    confidence=0.9,
                    bbox_xyxy=[10, 20, 30, 40],
                    source="full_frame_yolo",
                )
            ])
            decision = gate.process(_packet(frame_id=1))

        self.assertEqual(decision.trigger_type, TriggerType.ROI)
        self.assertEqual(decision.decision_reason, "reference_feedback")
        self.assertEqual(decision.rois[0].xywh(), [10, 20, 20, 20])
        self.assertEqual(decision.feedback_candidate_count, 1)
        self.assertEqual(decision.feedback_assisted_roi_count, 1)
        self.assertEqual(decision.feedback_active_track_count, 1)

    def test_reference_feedback_drops_candidate_that_overlaps_policy_roi(self) -> None:
        gate = RuleBasedRoiGenerator(
            RoiGeneratorConfig(
                full_frame_interval=60,
                reference_feedback_enabled=True,
                reference_feedback_ttl_frames=5,
                reference_feedback_margin_ratio=0.0,
                reference_feedback_duplicate_overlap_ratio=0.5,
            ),
            policy=FakePolicy([ROI(x=10, y=10, w=30, h=30, coord_system="original_frame")]),
        )

        with _patched_gate_helpers():
            gate.process(_packet(frame_id=0))
            gate.update_reference_feedback([
                Detection(
                    camera_id="cam_test",
                    frame_id=0,
                    class_id=0,
                    class_name="person",
                    confidence=0.9,
                    bbox_xyxy=[20, 20, 40, 40],
                    source="full_frame_yolo",
                )
            ])
            decision = gate.process(_packet(frame_id=1))

        self.assertEqual(decision.trigger_type, TriggerType.ROI)
        self.assertEqual(len(decision.rois), 1)
        self.assertEqual(decision.feedback_candidate_count, 1)
        self.assertEqual(decision.feedback_assisted_roi_count, 0)

    def test_reference_feedback_expires_after_ttl(self) -> None:
        gate = RuleBasedRoiGenerator(
            RoiGeneratorConfig(
                full_frame_interval=60,
                reference_feedback_enabled=True,
                reference_feedback_ttl_frames=1,
                reference_feedback_margin_ratio=0.0,
            ),
            policy=FakePolicy([]),
        )

        with _patched_gate_helpers():
            gate.process(_packet(frame_id=0))
            gate.update_reference_feedback([
                Detection(
                    camera_id="cam_test",
                    frame_id=0,
                    class_id=0,
                    class_name="person",
                    confidence=0.9,
                    bbox_xyxy=[10, 20, 30, 40],
                    source="full_frame_yolo",
                )
            ])
            decision = gate.process(_packet(frame_id=2))

        self.assertEqual(decision.trigger_type, TriggerType.NONE)
        self.assertEqual(decision.feedback_candidate_count, 0)
        self.assertEqual(decision.feedback_stale_track_count, 1)

    def test_debug_sink_receives_per_frame_generation_trace(self) -> None:
        sink = FakeDebugSink()
        gate = RuleBasedRoiGenerator(
            RoiGeneratorConfig(full_frame_interval=60),
            debug_sink=sink,
            policy=FakePolicy([ROI(x=10, y=10, w=20, h=20, coord_system="analysis_frame")]),
        )

        with _patched_gate_helpers():
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
        self.assertEqual(evaluate_budget_fallback(rois, FrameSize(100, 100), config).reason, "batch_slot_overflow")

    def test_should_fallback_when_roi_area_exceeds_limit(self) -> None:
        config = RoiGeneratorConfig(max_total_roi_area_ratio=0.25)
        rois = [ROI(0, 0, 60, 60)]
        self.assertTrue(should_fallback_to_full_frame(rois, FrameSize(100, 100), config))
        self.assertEqual(evaluate_budget_fallback(rois, FrameSize(100, 100), config).reason, "roi_area_near_full_frame")

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


class FakePolicy:
    def __init__(self, final_rois: list[ROI], name: str = "fake_policy", selected_tile_count: int = 0) -> None:
        self.final_rois = final_rois
        self.name = name
        self.selected_tile_count = selected_tile_count

    def generate(self, event_maps, analysis_size: FrameSize, original_size: FrameSize):
        from roi_generator.observability.trace import RoiGenerationTrace, TileTrace

        final_rois = [
            ROI(roi.x, roi.y, roi.w, roi.h, score=roi.score, coord_system="original_frame")
            for roi in self.final_rois
        ]
        tile_traces = [
            TileTrace(
                tile_id=index,
                row=0,
                col=index - 1,
                bbox=ROI(x=0, y=0, w=1, h=1, coord_system="original_frame"),
                motion_density=1.0,
                selected=True,
            )
            for index in range(1, self.selected_tile_count + 1)
        ]
        return RoiGenerationTrace(
            filtered_motion_map=event_maps.motion_map,
            candidate_analysis_rois=self.final_rois,
            merged_analysis_rois=self.final_rois,
            final_rois=final_rois,
            tile_traces=tile_traces,
        )


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


def _patched_gate_helpers(rois: list[ROI] | None = None, seen_sizes: list[FrameSize] | None = None):
    def resize(gray, analysis_size):
        if seen_sizes is not None:
            seen_sizes.append(analysis_size)
        return FakeGrayFrame()

    patches = {
        "to_gray": lambda frame: FakeGrayFrame(),
        "resize_for_analysis": resize,
        "encode_event_maps": lambda **kwargs: FakeEventMaps(),
    }
    if rois is not None:
        patches["create_roi_policy"] = lambda config: FakePolicy(rois)
    return patch.multiple("roi_generator.core.gate", **patches)


if __name__ == "__main__":
    unittest.main()
