from __future__ import annotations

import unittest

from common import FrameSize, GroundTruthAnnotation
from evaluation.reports.static_zone_prior import (
    GridShape,
    StaticZoneProfile,
    build_static_zone_prior_report,
    evaluate_static_zone_profile,
)


class StaticZonePriorReportTest(unittest.TestCase):
    def test_top_cells_capture_dense_center_region(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = GridShape(columns=10, rows=10)
        records = [
            _gt(frame_id=0, bbox=[10, 10, 20, 20]),
            _gt(frame_id=1, bbox=[10, 10, 20, 20]),
            _gt(frame_id=2, bbox=[80, 80, 90, 90]),
        ]

        report, cells = build_static_zone_prior_report(
            ground_truth=records,
            frame_count=3,
            frame_size=frame_size,
            grid_shape=grid_shape,
            profiles=[StaticZoneProfile(name="top_01", max_area_ratio=0.01)],
            dataset_config="sample.yaml",
            experiment_name="sample",
            target_classes=["person"],
        )

        profile = report.profiles["top_01"]
        self.assertEqual(profile.selected_cell_count, 1)
        self.assertAlmostEqual(profile.selected_area_ratio, 0.01)
        self.assertEqual(profile.center_contained_gt_count, 2)
        self.assertAlmostEqual(profile.center_gt_recall, 2 / 3)
        self.assertEqual(report.occupied_cell_count, 2)
        self.assertEqual(sum(1 for cell in cells if cell.center_hit_count > 0), 2)

    def test_bbox_recall_requires_all_overlapped_cells(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = GridShape(columns=10, rows=10)
        records = [_gt(frame_id=0, bbox=[10, 10, 29, 29])]

        report = evaluate_static_zone_profile(
            ground_truth=records,
            gt_by_frame={("cam", 0): records},
            frame_size=frame_size,
            grid_shape=grid_shape,
            profile=StaticZoneProfile(name="manual", max_area_ratio=0.01),
            selected_cells={(1, 1)},
        )

        self.assertEqual(report.center_contained_gt_count, 1)
        self.assertEqual(report.bbox_contained_gt_count, 0)
        self.assertEqual(report.center_contained_target_frame_count, 1)
        self.assertEqual(report.bbox_contained_target_frame_count, 0)

    def test_dilation_can_turn_center_prior_into_bbox_containment(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = GridShape(columns=10, rows=10)
        records = [_gt(frame_id=0, bbox=[10, 10, 29, 29])]

        report, _ = build_static_zone_prior_report(
            ground_truth=records,
            frame_count=1,
            frame_size=frame_size,
            grid_shape=grid_shape,
            profiles=[
                StaticZoneProfile(name="top_01", max_area_ratio=0.01),
                StaticZoneProfile(name="top_01_dilate1", max_area_ratio=0.01, dilation_cells=1),
            ],
            dataset_config="sample.yaml",
            experiment_name="sample",
            target_classes=["person"],
        )

        self.assertEqual(report.profiles["top_01"].bbox_contained_gt_count, 0)
        self.assertEqual(report.profiles["top_01_dilate1"].bbox_contained_gt_count, 1)
        self.assertGreater(report.profiles["top_01_dilate1"].selected_area_ratio, 0.01)


def _gt(frame_id: int, bbox: list[float]) -> GroundTruthAnnotation:
    return GroundTruthAnnotation(
        camera_id="cam",
        frame_id=frame_id,
        class_id=0,
        class_name="person",
        bbox_xyxy=bbox,
        annotation_id=f"gt-{frame_id}",
        image_id=frame_id,
        file_name=f"{frame_id}.jpg",
    )


if __name__ == "__main__":
    unittest.main()
