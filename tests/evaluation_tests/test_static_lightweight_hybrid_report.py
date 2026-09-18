from __future__ import annotations

import unittest

from common import FrameSize, GroundTruthAnnotation
from evaluation.reports.static_lightweight_hybrid import (
    GridShape,
    StaticLightweightFrameScores,
    StaticLightweightProfile,
    build_static_lightweight_report,
    evaluate_static_lightweight_profile,
)


class StaticLightweightHybridReportTest(unittest.TestCase):
    def test_static_only_profile_matches_static_cells(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = GridShape(columns=10, rows=10)
        frame_scores = [_scores(0, frame_size, hot_index=99)]
        gt_by_frame = {("cam", 0): [_gt(0, [0, 0, 9, 9])]}
        profile = StaticLightweightProfile(
            name="static_only",
            static_max_area_ratio=0.01,
            static_dilation_cells=0,
            signal_name="hybrid",
            extra_budget_ratio=0.0,
        )

        report, _ = evaluate_static_lightweight_profile(
            frame_scores, gt_by_frame, static_selected_cells={(0, 0)}, grid_shape=grid_shape, profile=profile
        )

        self.assertEqual(report.bbox_contained_gt_count, 1)
        self.assertEqual(report.static_only_bbox_contained_gt_count, 1)
        self.assertAlmostEqual(report.incremental_bbox_gt_recall, 0.0)
        self.assertAlmostEqual(report.selected_area_ratio, 0.01)

    def test_budgeted_signal_cell_recovers_target_outside_static_cell(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = GridShape(columns=10, rows=10)
        frame_scores = [_scores(0, frame_size, hot_index=11)]
        gt_by_frame = {("cam", 0): [_gt(0, [10, 10, 19, 19])]}
        profile = StaticLightweightProfile(
            name="budget_recovers",
            static_max_area_ratio=0.01,
            static_dilation_cells=0,
            signal_name="hybrid",
            extra_budget_ratio=0.01,
        )

        report, _ = evaluate_static_lightweight_profile(
            frame_scores, gt_by_frame, static_selected_cells={(0, 0)}, grid_shape=grid_shape, profile=profile
        )

        self.assertEqual(report.static_only_bbox_contained_gt_count, 0)
        self.assertEqual(report.bbox_contained_gt_count, 1)
        self.assertAlmostEqual(report.incremental_bbox_gt_recall, 1.0)

    def test_combined_dilation_recovers_target_spanning_cells(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = GridShape(columns=10, rows=10)
        frame_scores = [_scores(0, frame_size, hot_index=11)]
        gt_by_frame = {("cam", 0): [_gt(0, [10, 10, 29, 29])]}
        profile_no_dilation = StaticLightweightProfile(
            name="no_dilation",
            static_max_area_ratio=0.01,
            static_dilation_cells=0,
            signal_name="hybrid",
            extra_budget_ratio=0.01,
            combined_dilation_cells=0,
        )
        profile_dilated = StaticLightweightProfile(
            name="dilated",
            static_max_area_ratio=0.01,
            static_dilation_cells=0,
            signal_name="hybrid",
            extra_budget_ratio=0.01,
            combined_dilation_cells=1,
        )

        no_dilation, _ = evaluate_static_lightweight_profile(
            frame_scores, gt_by_frame, static_selected_cells={(0, 0)}, grid_shape=grid_shape, profile=profile_no_dilation
        )
        dilated, _ = evaluate_static_lightweight_profile(
            frame_scores, gt_by_frame, static_selected_cells={(0, 0)}, grid_shape=grid_shape, profile=profile_dilated
        )

        self.assertEqual(no_dilation.bbox_contained_gt_count, 0)
        self.assertEqual(dilated.bbox_contained_gt_count, 1)

    def test_build_report_preserves_profiles(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = GridShape(columns=10, rows=10)
        report, records = build_static_lightweight_report(
            frame_scores=[
                _scores(0, frame_size, hot_index=11),
                _scores(1, frame_size, hot_index=88),
            ],
            ground_truth=[
                _gt(0, [10, 10, 20, 20]),
                _gt(1, [80, 80, 90, 90]),
            ],
            profiles=[
                StaticLightweightProfile(
                    name="edge_budget_01",
                    static_max_area_ratio=0.01,
                    static_dilation_cells=0,
                    signal_name="edge",
                    extra_budget_ratio=0.01,
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
        self.assertEqual(tuple(report.profiles.keys()), ("edge_budget_01",))
        self.assertEqual(report.target_classes, ("person",))
        self.assertEqual(len(records), 2)


def _scores(frame_id: int, frame_size: FrameSize, hot_index: int) -> StaticLightweightFrameScores:
    scores = [0.0 for _ in range(100)]
    scores[hot_index] = 1.0
    return StaticLightweightFrameScores(
        camera_id="cam",
        frame_id=frame_id,
        frame_index=frame_id,
        frame_size=frame_size,
        scores_by_signal={"edge": tuple(scores), "texture": tuple(scores), "hybrid": tuple(scores)},
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
