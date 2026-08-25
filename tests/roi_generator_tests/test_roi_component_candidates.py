from __future__ import annotations

import unittest

import numpy as np

from common import FrameSize, ROI
from roi_generator.candidates.components import component_traces_from_rois, count_connected_components, motion_density


class ComponentCandidateMetadataTest(unittest.TestCase):
    def test_component_traces_from_rois_calculates_geometry_metrics(self) -> None:
        traces = component_traces_from_rois(
            [ROI(x=2, y=4, w=10, h=5, score=0.0025, coord_system="analysis_frame")],
            FrameSize(width=100, height=100),
        )

        trace = traces[0]

        self.assertEqual(trace.component_id, 1)
        self.assertEqual(trace.bbox.xywh(), [2, 4, 10, 5])
        self.assertEqual(trace.component_area_ratio, 0.0025)
        self.assertEqual(trace.bbox_width, 10)
        self.assertEqual(trace.bbox_height, 5)
        self.assertEqual(trace.bbox_aspect_ratio, 2.0)
        self.assertEqual(trace.fill_density, 0.5)
        self.assertEqual(trace.center_x, 7.0)
        self.assertEqual(trace.center_y, 6.5)

    def test_motion_component_summary_helpers(self) -> None:
        motion_map = np.zeros((4, 4), dtype="uint8")
        motion_map[0, 0] = 255
        motion_map[3, 3] = 255

        self.assertEqual(count_connected_components(motion_map), 2)
        self.assertEqual(motion_density(motion_map), 2 / 16)


if __name__ == "__main__":
    unittest.main()
