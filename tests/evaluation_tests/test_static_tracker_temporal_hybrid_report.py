from __future__ import annotations

import unittest

from common import FrameSize, GroundTruthAnnotation
from evaluation.reports.static_tracker_temporal_hybrid import (
    GridShape,
    StaticTrackerHybridFrame,
    StaticTrackerHybridProfile,
    build_static_tracker_hybrid_report,
    evaluate_static_tracker_hybrid_profile,
)


class StaticTrackerTemporalHybridReportTest(unittest.TestCase):
    def test_static_prior_recovers_targets_tracker_memory_misses(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = GridShape(columns=10, rows=10)
        frames = [_frame(index, frame_size) for index in range(4)]
        gt_by_frame = {
            ("cam", 0): [_gt(0, [50, 50, 60, 60])],
            ("cam", 1): [_gt(1, [0, 0, 9, 9])],
            ("cam", 2): [_gt(2, [50, 50, 60, 60])],
            ("cam", 3): [_gt(3, [0, 0, 9, 9])],
        }
        profile = StaticTrackerHybridProfile(
            name="static_only_recovers",
            static_max_area_ratio=0.01,
            static_dilation_cells=0,
            refresh_interval=2,
            margin_ratio=0.0,
            guard_stale_frames=2,
        )

        report, records = evaluate_static_tracker_hybrid_profile(
            frames, gt_by_frame, static_selected_cells={(0, 0)}, grid_shape=grid_shape, profile=profile
        )

        self.assertEqual(report.refresh_frame_count, 2)
        self.assertEqual(report.memory_frame_count, 2)
        self.assertEqual(report.memory_frame_target_gt_count, 2)
        self.assertEqual(report.static_only_contained_gt_count, 2)
        self.assertEqual(report.memory_frame_contained_gt_count, 2)
        self.assertEqual(report.contained_gt_count, 4)
        self.assertAlmostEqual(report.target_gt_recall, 1.0)
        self.assertEqual(len(records), 4)

    def test_tracker_memory_recovers_targets_outside_static_cell(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = GridShape(columns=10, rows=10)
        frames = [_frame(index, frame_size) for index in range(2)]
        gt_by_frame = {
            ("cam", 0): [_gt(0, [20, 20, 30, 30])],
            ("cam", 1): [_gt(1, [21, 20, 29, 29])],
        }
        profile = StaticTrackerHybridProfile(
            name="memory_recovers",
            static_max_area_ratio=0.01,
            static_dilation_cells=0,
            refresh_interval=2,
            margin_ratio=0.0,
            guard_stale_frames=2,
        )

        report, _ = evaluate_static_tracker_hybrid_profile(
            frames, gt_by_frame, static_selected_cells={(5, 5)}, grid_shape=grid_shape, profile=profile
        )

        self.assertEqual(report.static_only_contained_gt_count, 0)
        self.assertEqual(report.memory_frame_contained_gt_count, 1)
        self.assertEqual(report.static_recovered_gt_count, 1)

    def test_guard_stale_frames_trigger_fallback_after_expiry(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = GridShape(columns=10, rows=10)
        frames = [_frame(index, frame_size) for index in range(4)]
        gt_by_frame = {("cam", 0): [_gt(0, [0, 0, 9, 9])]}
        profile = StaticTrackerHybridProfile(
            name="guard_expiry",
            static_max_area_ratio=0.01,
            static_dilation_cells=0,
            refresh_interval=4,
            margin_ratio=0.0,
            guard_stale_frames=1,
        )

        report, records = evaluate_static_tracker_hybrid_profile(
            frames, gt_by_frame, static_selected_cells={(9, 9)}, grid_shape=grid_shape, profile=profile
        )

        self.assertEqual(report.guard_fallback_frame_count, 2)
        self.assertFalse(records[1].guard_fallback)
        self.assertTrue(records[2].guard_fallback)
        self.assertTrue(records[3].guard_fallback)

    def test_build_report_preserves_profile_mapping(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = GridShape(columns=10, rows=10)
        frames = [_frame(index, frame_size) for index in range(2)]
        gt = [_gt(0, [10, 10, 20, 20]), _gt(1, [10, 10, 20, 20])]

        report, records = build_static_tracker_hybrid_report(
            frames=frames,
            ground_truth=gt,
            profiles=[
                StaticTrackerHybridProfile(
                    name="refresh_1",
                    static_max_area_ratio=0.1,
                    static_dilation_cells=0,
                    refresh_interval=1,
                    margin_ratio=0.0,
                    guard_stale_frames=1,
                )
            ],
            grid_shape=grid_shape,
            frame_size=frame_size,
            dataset_config="sample.yaml",
            experiment_name="sample",
            target_classes=["person"],
        )

        self.assertEqual(report.frame_count, 2)
        self.assertEqual(report.target_gt_count, 2)
        self.assertEqual(tuple(report.profiles.keys()), ("refresh_1",))
        self.assertEqual(report.target_classes, ("person",))
        self.assertEqual(len(records), 2)


def _frame(index: int, frame_size: FrameSize) -> StaticTrackerHybridFrame:
    return StaticTrackerHybridFrame(
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
