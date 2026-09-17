from __future__ import annotations

import unittest

from common import FrameSize, GroundTruthAnnotation
from evaluation.reports.tracker_memory import (
    TrackerMemoryFrame,
    TrackerMemoryProfile,
    build_tracker_memory_report,
    evaluate_tracker_memory_profile,
)


class TrackerMemoryReportTest(unittest.TestCase):
    def test_refresh_every_two_uses_memory_on_intermediate_frames(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        frames = [_frame(index, frame_size) for index in range(4)]
        gt_by_frame = {
            ("cam", 0): [_gt(0, [10, 10, 20, 20])],
            ("cam", 1): [_gt(1, [11, 10, 21, 20])],
            ("cam", 2): [_gt(2, [40, 40, 50, 50])],
            ("cam", 3): [_gt(3, [41, 40, 51, 50])],
        }

        report, records = evaluate_tracker_memory_profile(
            frames,
            gt_by_frame,
            TrackerMemoryProfile(
                name="refresh_2_margin_20",
                refresh_interval=2,
                margin_ratio=0.2,
                ttl_frames=2,
            ),
        )

        self.assertEqual(report.refresh_frame_count, 2)
        self.assertEqual(report.memory_frame_count, 2)
        self.assertEqual(report.target_gt_count, 4)
        self.assertEqual(report.contained_gt_count, 4)
        self.assertEqual(report.memory_frame_target_gt_count, 2)
        self.assertEqual(report.memory_frame_contained_gt_count, 2)
        self.assertAlmostEqual(report.full_frame_detector_call_reduction, 0.5)
        self.assertEqual(len(records), 4)
        self.assertFalse(records[1].is_refresh_frame)

    def test_stale_memory_loses_recall_when_object_moves_outside_margin(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        frames = [_frame(index, frame_size) for index in range(3)]
        gt_by_frame = {
            ("cam", 0): [_gt(0, [10, 10, 20, 20])],
            ("cam", 1): [_gt(1, [70, 70, 80, 80])],
            ("cam", 2): [_gt(2, [70, 70, 80, 80])],
        }

        report, _ = evaluate_tracker_memory_profile(
            frames,
            gt_by_frame,
            TrackerMemoryProfile(
                name="refresh_3_margin_10",
                refresh_interval=3,
                margin_ratio=0.1,
                ttl_frames=3,
            ),
        )

        self.assertEqual(report.refresh_frame_count, 1)
        self.assertEqual(report.memory_frame_target_gt_count, 2)
        self.assertEqual(report.memory_frame_contained_gt_count, 0)
        self.assertAlmostEqual(report.target_gt_recall, 1 / 3)
        self.assertEqual(report.max_consecutive_memory_miss_frames, 2)

    def test_build_report_preserves_profile_mapping(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        frames = [_frame(index, frame_size) for index in range(2)]
        gt = [_gt(0, [10, 10, 20, 20]), _gt(1, [10, 10, 20, 20])]

        report, records = build_tracker_memory_report(
            frames=frames,
            ground_truth=gt,
            profiles=[
                TrackerMemoryProfile(
                    name="refresh_1",
                    refresh_interval=1,
                    margin_ratio=0.0,
                    ttl_frames=1,
                )
            ],
            dataset_config="sample.yaml",
            experiment_name="sample",
            target_classes=["person"],
        )

        self.assertEqual(report.frame_count, 2)
        self.assertEqual(report.target_gt_count, 2)
        self.assertEqual(tuple(report.profiles.keys()), ("refresh_1",))
        self.assertEqual(report.target_classes, ("person",))
        self.assertEqual(len(records), 2)


def _frame(index: int, frame_size: FrameSize) -> TrackerMemoryFrame:
    return TrackerMemoryFrame(
        camera_id="cam",
        frame_id=index,
        frame_index=index,
        timestamp=float(index),
        frame_size=frame_size,
    )


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
