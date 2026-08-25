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
