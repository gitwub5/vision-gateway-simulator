from __future__ import annotations

import unittest

from common import FrameSize, GroundTruthAnnotation
from evaluation.reports.lightweight_visual_signal import (
    FrameSignalScores,
    LightweightSignalProfile,
    SignalGridShape,
    build_lightweight_signal_report,
    evaluate_lightweight_signal_profile,
)


class LightweightVisualSignalReportTest(unittest.TestCase):
    def test_top_signal_cells_capture_target_center(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = SignalGridShape(columns=10, rows=10)
        frame_scores = [
            _scores(
                frame_id=0,
                frame_size=frame_size,
                hot_index=11,
                signal_name="edge",
            )
        ]
        gt_by_frame = {("cam", 0): [_gt(0, [10, 10, 20, 20])]}

        report, records = evaluate_lightweight_signal_profile(
            frame_scores=frame_scores,
            gt_by_frame=gt_by_frame,
            profile=LightweightSignalProfile(
                name="edge_top_01",
                signal_name="edge",
                max_area_ratio=0.01,
            ),
            grid_shape=grid_shape,
        )

        self.assertEqual(report.center_contained_gt_count, 1)
        self.assertEqual(report.bbox_contained_gt_count, 1)
        self.assertAlmostEqual(report.center_gt_recall, 1.0)
        self.assertEqual(records[0].selected_cell_count, 1)

    def test_bbox_recall_needs_dilation_when_object_crosses_cells(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = SignalGridShape(columns=10, rows=10)
        frame_scores = [
            _scores(
                frame_id=0,
                frame_size=frame_size,
                hot_index=11,
                signal_name="hybrid",
            )
        ]
        gt_by_frame = {("cam", 0): [_gt(0, [10, 10, 29, 29])]}

        no_dilation, _ = evaluate_lightweight_signal_profile(
            frame_scores=frame_scores,
            gt_by_frame=gt_by_frame,
            profile=LightweightSignalProfile(
                name="hybrid_top_01",
                signal_name="hybrid",
                max_area_ratio=0.01,
            ),
            grid_shape=grid_shape,
        )
        dilated, _ = evaluate_lightweight_signal_profile(
            frame_scores=frame_scores,
            gt_by_frame=gt_by_frame,
            profile=LightweightSignalProfile(
                name="hybrid_top_01_dilate1",
                signal_name="hybrid",
                max_area_ratio=0.01,
                dilation_cells=1,
            ),
            grid_shape=grid_shape,
        )

        self.assertEqual(no_dilation.center_contained_gt_count, 1)
        self.assertEqual(no_dilation.bbox_contained_gt_count, 0)
        self.assertEqual(dilated.bbox_contained_gt_count, 1)

    def test_build_report_preserves_profiles(self) -> None:
        frame_size = FrameSize(width=100, height=100)
        grid_shape = SignalGridShape(columns=10, rows=10)
        report, records = build_lightweight_signal_report(
            frame_scores=[
                _scores(0, frame_size, hot_index=11, signal_name="edge"),
                _scores(1, frame_size, hot_index=88, signal_name="edge"),
            ],
            ground_truth=[
                _gt(0, [10, 10, 20, 20]),
                _gt(1, [80, 80, 90, 90]),
            ],
            profiles=[
                LightweightSignalProfile(
                    name="edge_top_01",
                    signal_name="edge",
                    max_area_ratio=0.01,
                )
            ],
            grid_shape=grid_shape,
            dataset_config="sample.yaml",
            experiment_name="sample",
            target_classes=["person"],
        )

        self.assertEqual(report.frame_count, 2)
        self.assertEqual(report.target_gt_count, 2)
        self.assertEqual(tuple(report.profiles.keys()), ("edge_top_01",))
        self.assertEqual(report.target_classes, ("person",))
        self.assertEqual(len(records), 2)


def _scores(
    frame_id: int,
    frame_size: FrameSize,
    hot_index: int,
    signal_name: str,
) -> FrameSignalScores:
    scores = [0.0 for _ in range(100)]
    scores[hot_index] = 1.0
    return FrameSignalScores(
        camera_id="cam",
        frame_id=frame_id,
        frame_index=frame_id,
        frame_size=frame_size,
        scores_by_signal={signal_name: tuple(scores)},
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
