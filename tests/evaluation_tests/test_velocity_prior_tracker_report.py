from __future__ import annotations

import unittest

from common import FrameSize, GroundTruthAnnotation
from evaluation.reports.velocity_prior_tracker import (
    VelocityTrackerFrame,
    VelocityTrackerProfile,
    build_velocity_tracker_report,
    evaluate_velocity_tracker_profile,
)


class VelocityPriorTrackerReportTest(unittest.TestCase):
    def test_velocity_prediction_covers_moving_object_between_refreshes(self) -> None:
        frames = [_frame(index) for index in range(4)]
        gt_by_frame = {
            ("cam", 0): [_gt(0, [10, 10, 20, 20])],
            ("cam", 1): [_gt(1, [20, 10, 30, 20])],
            ("cam", 2): [_gt(2, [30, 10, 40, 20])],
            ("cam", 3): [_gt(3, [40, 10, 50, 20])],
        }
        hold_report, _ = evaluate_velocity_tracker_profile(
            frames,
            gt_by_frame,
            VelocityTrackerProfile(
                name="hold",
                refresh_interval=2,
                ttl_frames=2,
                margin_ratio=0.0,
                use_velocity=False,
                max_match_distance_ratio=0.30,
            ),
        )
        velocity_report, _ = evaluate_velocity_tracker_profile(
            frames,
            gt_by_frame,
            VelocityTrackerProfile(
                name="velocity",
                refresh_interval=2,
                ttl_frames=2,
                margin_ratio=0.0,
                use_velocity=True,
                max_match_distance_ratio=0.30,
            ),
        )

        self.assertLess(
            hold_report.memory_frame_target_gt_recall,
            velocity_report.memory_frame_target_gt_recall,
        )

    def test_build_report_preserves_profiles(self) -> None:
        frames = [_frame(index) for index in range(2)]
        report, records = build_velocity_tracker_report(
            frames=frames,
            ground_truth=[
                _gt(0, [10, 10, 20, 20]),
                _gt(1, [10, 10, 20, 20]),
            ],
            profiles=[
                VelocityTrackerProfile(
                    name="hold",
                    refresh_interval=1,
                    ttl_frames=1,
                    margin_ratio=0.0,
                    use_velocity=False,
                )
            ],
            dataset_config="sample.yaml",
            experiment_name="sample",
            target_classes=["car"],
        )

        self.assertEqual(report.frame_count, 2)
        self.assertEqual(report.target_gt_count, 2)
        self.assertEqual(tuple(report.profiles.keys()), ("hold",))
        self.assertEqual(len(records), 2)


def _frame(frame_index: int) -> VelocityTrackerFrame:
    return VelocityTrackerFrame(
        camera_id="cam",
        frame_id=frame_index,
        frame_index=frame_index,
        timestamp=float(frame_index),
        frame_size=FrameSize(width=100, height=100),
    )


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
