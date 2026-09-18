from __future__ import annotations

import unittest

from common import FrameSize, GroundTruthAnnotation
from evaluation.reports.road_region_prior import (
    RoadGridShape,
    RoadRegionPriorProfile,
    build_road_region_prior_report,
    evaluate_road_region_prior_profile,
)


class RoadRegionPriorReportTest(unittest.TestCase):
    def test_bbox_envelope_covers_wide_object_with_row_range(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = RoadGridShape(columns=10, rows=10)
        gt = [_gt(0, [10, 40, 40, 60])]
        report, _ = build_road_region_prior_report(
            ground_truth=gt,
            frame_count=1,
            frame_size=frame_size,
            grid_shape=grid_shape,
            profiles=[
                RoadRegionPriorProfile(
                    name="bbox_envelope",
                    bbox_based=True,
                )
            ],
            dataset_config="sample.yaml",
            experiment_name="sample",
            target_classes=["car"],
        )

        profile = report.profiles["bbox_envelope"]
        self.assertEqual(profile.bbox_gt_recall, 1.0)
        self.assertEqual(profile.center_gt_recall, 1.0)

    def test_center_envelope_can_miss_bbox_extent(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = RoadGridShape(columns=10, rows=10)
        gt = [_gt(0, [10, 40, 40, 60])]
        profile = RoadRegionPriorProfile(name="center", bbox_based=False)
        report = evaluate_road_region_prior_profile(
            ground_truth=gt,
            gt_by_frame={("cam", 0): gt},
            frame_size=frame_size,
            grid_shape=grid_shape,
            profile=profile,
            selected_cells={(5, 2)},
        )

        self.assertEqual(report.center_gt_recall, 1.0)
        self.assertEqual(report.bbox_gt_recall, 0.0)


def _gt(frame_id: int, bbox: list[float]) -> GroundTruthAnnotation:
    return GroundTruthAnnotation(
        camera_id="cam",
        frame_id=frame_id,
        class_id=0,
        class_name="car",
        bbox_xyxy=bbox,
        annotation_id=f"gt-{frame_id}",
        image_id=frame_id,
        file_name=f"{frame_id}.jpg",
    )


if __name__ == "__main__":
    unittest.main()
