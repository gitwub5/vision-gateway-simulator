from __future__ import annotations

import unittest

import numpy as np

from common import FrameSize
from roi_generator.core.config import RoiGeneratorConfig
from roi_generator.policies import create_roi_policy
from roi_generator.policies.component_bbox import ComponentBboxPolicy
from roi_generator.policies.hybrid_component_tile import HybridComponentTilePolicy
from roi_generator.policies.tile_mask import TileMaskPolicy
from roi_generator.signals.event_encoder import EventMaps


class RoiPolicyBaselineTest(unittest.TestCase):
    def test_policy_factory_selects_configured_policy(self) -> None:
        self.assertIsInstance(create_roi_policy(RoiGeneratorConfig()), ComponentBboxPolicy)
        self.assertIsInstance(create_roi_policy(RoiGeneratorConfig(roi_policy="tile_mask")), TileMaskPolicy)
        self.assertIsInstance(
            create_roi_policy(RoiGeneratorConfig(roi_policy="hybrid_component_tile")),
            HybridComponentTilePolicy,
        )

    def test_policy_factory_rejects_unknown_policy(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported roi_policy"):
            create_roi_policy(RoiGeneratorConfig(roi_policy="unknown"))

    def test_component_noise_filter_drops_sparse_wide_component(self) -> None:
        motion_map = np.zeros((20, 20), dtype="uint8")
        motion_map[10, 1:19] = 255
        policy = ComponentBboxPolicy(
            RoiGeneratorConfig(
                morphology_kernel_size=1,
                min_area_ratio=0.0,
                component_filter_enabled=True,
                component_filter_max_aspect_ratio=4.0,
            )
        )

        trace = policy.generate(
            _event_maps(motion_map),
            analysis_size=FrameSize(20, 20),
            original_size=FrameSize(20, 20),
        )

        self.assertEqual(len(trace.candidate_analysis_rois), 1)
        self.assertEqual(trace.final_rois, [])

    def test_component_recall_padding_expands_small_roi(self) -> None:
        motion_map = np.zeros((20, 20), dtype="uint8")
        motion_map[9:11, 9:11] = 255
        policy = ComponentBboxPolicy(
            RoiGeneratorConfig(
                morphology_kernel_size=1,
                min_area_ratio=0.0,
                margin_ratio=0.0,
                min_final_roi_width=10,
                min_final_roi_height=8,
            )
        )

        trace = policy.generate(
            _event_maps(motion_map),
            analysis_size=FrameSize(20, 20),
            original_size=FrameSize(20, 20),
        )

        self.assertEqual(len(trace.final_rois), 1)
        self.assertEqual(trace.final_rois[0].w, 10)
        self.assertEqual(trace.final_rois[0].h, 8)

    def test_tile_mask_generates_roi_from_selected_tiles(self) -> None:
        motion_map = np.zeros((4, 4), dtype="uint8")
        motion_map[0:2, 0:2] = 255
        policy = TileMaskPolicy(
            RoiGeneratorConfig(
                morphology_kernel_size=1,
                tile_grid_rows=2,
                tile_grid_cols=2,
                tile_motion_density_threshold=0.5,
            )
        )

        trace = policy.generate(
            _event_maps(motion_map),
            analysis_size=FrameSize(4, 4),
            original_size=FrameSize(40, 40),
        )

        self.assertEqual(len(trace.final_rois), 1)
        self.assertEqual(trace.final_rois[0].xywh(), [0, 0, 20, 20])
        self.assertEqual(sum(1 for tile in trace.tile_traces if tile.selected), 1)

    def test_tile_mask_small_object_boost_expands_selected_tile_roi(self) -> None:
        motion_map = np.zeros((4, 4), dtype="uint8")
        motion_map[0:2, 0:2] = 255
        policy = TileMaskPolicy(
            RoiGeneratorConfig(
                morphology_kernel_size=1,
                tile_grid_rows=2,
                tile_grid_cols=2,
                tile_motion_density_threshold=0.5,
                small_object_boost_enabled=True,
                tile_overlap_ratio=1.0,
            )
        )

        trace = policy.generate(
            _event_maps(motion_map),
            analysis_size=FrameSize(4, 4),
            original_size=FrameSize(40, 40),
        )

        self.assertEqual(len(trace.final_rois), 1)
        self.assertEqual(trace.final_rois[0].xywh(), [0, 0, 30, 30])
        selected_tiles = [tile for tile in trace.tile_traces if tile.selected]
        self.assertEqual(len(selected_tiles), 1)
        self.assertEqual(selected_tiles[0].bbox.xywh(), [0, 0, 20, 20])

    def test_tile_mask_adaptive_threshold_suppresses_repeated_weak_tile(self) -> None:
        weak_motion = np.zeros((10, 10), dtype="uint8")
        weak_motion[0, 0:2] = 255
        strong_motion = np.zeros((10, 10), dtype="uint8")
        strong_motion[0, 0:5] = 255
        policy = TileMaskPolicy(
            RoiGeneratorConfig(
                morphology_kernel_size=1,
                tile_grid_rows=1,
                tile_grid_cols=1,
                tile_motion_density_threshold=0.01,
                adaptive_tile_threshold_enabled=True,
                adaptive_tile_threshold_ema_alpha=1.0,
                adaptive_tile_threshold_multiplier=1.5,
            )
        )

        first = policy.generate(
            _event_maps(weak_motion),
            analysis_size=FrameSize(10, 10),
            original_size=FrameSize(10, 10),
        )
        second = policy.generate(
            _event_maps(weak_motion),
            analysis_size=FrameSize(10, 10),
            original_size=FrameSize(10, 10),
        )
        third = policy.generate(
            _event_maps(strong_motion),
            analysis_size=FrameSize(10, 10),
            original_size=FrameSize(10, 10),
        )

        self.assertTrue(first.tile_traces[0].selected)
        self.assertEqual(first.tile_traces[0].selection_reason, "motion_threshold")
        self.assertFalse(second.tile_traces[0].selected)
        self.assertEqual(second.tile_traces[0].motion_threshold, 0.03)
        self.assertEqual(second.tile_traces[0].selection_reason, "below_adaptive_threshold")
        self.assertTrue(third.tile_traces[0].selected)
        self.assertEqual(third.tile_traces[0].selection_reason, "adaptive_motion_threshold")

    def test_tile_mask_rare_guard_suppresses_rare_weak_tile_after_history(self) -> None:
        empty_motion = np.zeros((10, 10), dtype="uint8")
        weak_motion = np.zeros((10, 10), dtype="uint8")
        weak_motion[0, 0:2] = 255
        policy = TileMaskPolicy(
            RoiGeneratorConfig(
                morphology_kernel_size=1,
                tile_grid_rows=1,
                tile_grid_cols=1,
                tile_motion_density_threshold=0.01,
                rare_tile_guard_enabled=True,
                rare_tile_guard_min_history_frames=2,
                rare_tile_guard_max_activation_rate=0.0,
                rare_tile_guard_weak_density_max=0.03,
            )
        )

        policy.generate(
            _event_maps(empty_motion),
            analysis_size=FrameSize(10, 10),
            original_size=FrameSize(10, 10),
        )
        policy.generate(
            _event_maps(empty_motion),
            analysis_size=FrameSize(10, 10),
            original_size=FrameSize(10, 10),
        )
        guarded = policy.generate(
            _event_maps(weak_motion),
            analysis_size=FrameSize(10, 10),
            original_size=FrameSize(10, 10),
        )

        self.assertFalse(guarded.tile_traces[0].selected)
        self.assertEqual(guarded.tile_traces[0].selection_reason, "rare_tile_guard_suppressed")
        self.assertEqual(guarded.final_rois, [])

    def test_tile_mask_neighbor_rescue_selects_adjacent_weak_tile(self) -> None:
        motion_map = np.zeros((6, 6), dtype="uint8")
        motion_map[0:2, 0:2] = 255
        motion_map[0, 2:4] = 255
        motion_map[4, 4] = 255
        policy = TileMaskPolicy(
            RoiGeneratorConfig(
                morphology_kernel_size=1,
                tile_grid_rows=3,
                tile_grid_cols=3,
                tile_motion_density_threshold=0.5,
                neighbor_rescue_enabled=True,
                neighbor_rescue_min_density=0.25,
            )
        )

        trace = policy.generate(
            _event_maps(motion_map),
            analysis_size=FrameSize(6, 6),
            original_size=FrameSize(60, 60),
        )

        selected_by_reason = {
            tile.selection_reason: tile.bbox.xywh()
            for tile in trace.tile_traces
            if tile.selected
        }
        self.assertEqual(selected_by_reason["motion_threshold"], [0, 0, 20, 20])
        self.assertEqual(selected_by_reason["neighbor_motion_weak"], [20, 0, 20, 20])
        self.assertFalse(trace.tile_traces[8].selected)

    def test_tile_mask_neighbor_rescue_respects_added_tile_cap(self) -> None:
        motion_map = np.zeros((6, 6), dtype="uint8")
        motion_map[2:4, 2:4] = 255
        motion_map[0, 2:4] = 255
        motion_map[2:4, 0] = 255
        policy = TileMaskPolicy(
            RoiGeneratorConfig(
                morphology_kernel_size=1,
                tile_grid_rows=3,
                tile_grid_cols=3,
                tile_motion_density_threshold=0.5,
                neighbor_rescue_enabled=True,
                neighbor_rescue_min_density=0.25,
                neighbor_rescue_max_added_tiles=1,
            )
        )

        trace = policy.generate(
            _event_maps(motion_map),
            analysis_size=FrameSize(6, 6),
            original_size=FrameSize(6, 6),
        )

        rescue_tiles = [
            tile
            for tile in trace.tile_traces
            if tile.selection_reason == "neighbor_motion_weak"
        ]
        self.assertEqual(len(rescue_tiles), 1)
        self.assertEqual(sum(1 for tile in trace.tile_traces if tile.selected), 2)

    def test_hybrid_keeps_component_that_overlaps_selected_tile(self) -> None:
        motion_map = np.zeros((4, 4), dtype="uint8")
        motion_map[0:2, 0:2] = 255
        policy = HybridComponentTilePolicy(
            RoiGeneratorConfig(
                morphology_kernel_size=1,
                min_area_ratio=0.0,
                margin_ratio=0.0,
                tile_grid_rows=2,
                tile_grid_cols=2,
                tile_motion_density_threshold=0.5,
            )
        )

        trace = policy.generate(
            _event_maps(motion_map),
            analysis_size=FrameSize(4, 4),
            original_size=FrameSize(40, 40),
        )

        self.assertEqual(len(trace.candidate_analysis_rois), 1)
        self.assertEqual(len(trace.final_rois), 1)
        self.assertEqual(trace.final_rois[0].xywh(), [0, 0, 20, 20])


def _event_maps(motion_map) -> EventMaps:
    zeros = np.zeros_like(motion_map)
    return EventMaps(on_event=zeros, off_event=zeros, motion_map=motion_map)


if __name__ == "__main__":
    unittest.main()
