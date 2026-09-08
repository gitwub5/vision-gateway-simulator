from __future__ import annotations

import unittest

import numpy as np

from common import FrameSize
from roi_generator.candidates.tiles import scale_tile_traces_to_original, selected_tile_count, tile_traces_from_motion_map


class TileCandidateMetadataTest(unittest.TestCase):
    def test_tile_traces_from_motion_map_calculates_density_and_selection(self) -> None:
        motion_map = np.zeros((4, 4), dtype="uint8")
        motion_map[0:2, 0:2] = 255

        traces = tile_traces_from_motion_map(
            motion_map,
            frame_size=FrameSize(width=4, height=4),
            grid_rows=2,
            grid_cols=2,
            motion_density_threshold=0.5,
        )

        self.assertEqual(len(traces), 4)
        self.assertEqual(traces[0].tile_id, 1)
        self.assertEqual(traces[0].bbox.xywh(), [0, 0, 2, 2])
        self.assertEqual(traces[0].motion_density, 1.0)
        self.assertTrue(traces[0].selected)
        self.assertEqual(traces[1].motion_density, 0.0)
        self.assertFalse(traces[1].selected)
        self.assertEqual(selected_tile_count(traces), 1)

    def test_tile_traces_can_use_per_tile_thresholds(self) -> None:
        motion_map = np.ones((4, 4), dtype="uint8") * 255

        traces = tile_traces_from_motion_map(
            motion_map,
            frame_size=FrameSize(width=4, height=4),
            grid_rows=2,
            grid_cols=2,
            motion_density_threshold=0.5,
            tile_thresholds={(0, 0): 1.0},
        )

        self.assertFalse(traces[0].selected)
        self.assertEqual(traces[0].motion_threshold, 1.0)
        self.assertEqual(traces[0].selection_reason, "below_motion_threshold")
        self.assertTrue(traces[1].selected)
        self.assertEqual(traces[1].motion_threshold, 0.5)

    def test_scale_tile_traces_to_original_converts_bbox_coordinates(self) -> None:
        traces = tile_traces_from_motion_map(
            np.ones((4, 4), dtype="uint8") * 255,
            frame_size=FrameSize(width=4, height=4),
            grid_rows=2,
            grid_cols=2,
            motion_density_threshold=0.5,
        )

        scaled = scale_tile_traces_to_original(
            traces,
            analysis_size=FrameSize(width=4, height=4),
            original_size=FrameSize(width=40, height=20),
        )

        self.assertEqual(scaled[0].bbox.xywh(), [0, 0, 20, 10])
        self.assertEqual(scaled[0].bbox.coord_system, "original_frame")


if __name__ == "__main__":
    unittest.main()
