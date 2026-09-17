from __future__ import annotations

import unittest

from evaluation.reports.temporal_gate import (
    TemporalFrameRecord,
    TemporalGateProfile,
    build_temporal_gate_report,
    evaluate_temporal_gate_profile,
)


class TemporalGateReportTest(unittest.TestCase):
    def test_process_all_preserves_target_recall_without_reduction(self) -> None:
        records = [
            _record(index=0, target_gt_count=1),
            _record(index=1, target_gt_count=0),
            _record(index=2, target_gt_count=2),
        ]

        report = evaluate_temporal_gate_profile(
            records,
            TemporalGateProfile(name="process_all", mode="all"),
        )

        self.assertEqual(report.processed_frame_count, 3)
        self.assertEqual(report.skipped_frame_count, 0)
        self.assertEqual(report.target_frame_count, 2)
        self.assertEqual(report.processed_target_frame_count, 2)
        self.assertEqual(report.target_gt_count, 3)
        self.assertEqual(report.processed_target_gt_count, 3)
        self.assertEqual(report.detector_call_reduction, 0.0)
        self.assertEqual(report.target_frame_recall, 1.0)
        self.assertEqual(report.target_gt_recall, 1.0)

    def test_fixed_interval_counts_skipped_target_frames_and_gt(self) -> None:
        records = [
            _record(index=0, target_gt_count=1),
            _record(index=1, target_gt_count=2),
            _record(index=2, target_gt_count=0),
            _record(index=3, target_gt_count=1),
            _record(index=4, target_gt_count=1),
        ]

        report = evaluate_temporal_gate_profile(
            records,
            TemporalGateProfile(name="fixed_skip_2", mode="fixed_interval", interval=2),
        )

        self.assertEqual(report.processed_frame_count, 3)
        self.assertEqual(report.skipped_frame_count, 2)
        self.assertEqual(report.processed_target_frame_count, 2)
        self.assertEqual(report.skipped_target_frame_count, 2)
        self.assertEqual(report.processed_target_gt_count, 2)
        self.assertEqual(report.skipped_target_gt_count, 3)
        self.assertAlmostEqual(report.detector_call_reduction, 0.4)
        self.assertAlmostEqual(report.target_frame_recall, 0.5)
        self.assertAlmostEqual(report.target_gt_recall, 0.4)

    def test_scene_delta_profile_uses_threshold_and_refresh_interval(self) -> None:
        records = [
            _record(index=0, target_gt_count=0, scene_delta_mean=0.0),
            _record(index=1, target_gt_count=1, scene_delta_mean=0.01),
            _record(index=2, target_gt_count=1, scene_delta_mean=0.01),
            _record(index=3, target_gt_count=1, scene_delta_mean=0.01),
            _record(index=4, target_gt_count=1, scene_delta_mean=0.05),
        ]

        report = evaluate_temporal_gate_profile(
            records,
            TemporalGateProfile(
                name="stability",
                mode="scene_delta",
                scene_delta_threshold=0.02,
                max_refresh_interval=3,
            ),
        )

        self.assertEqual(report.processed_frame_count, 3)
        self.assertEqual(report.skipped_target_frame_count, 2)
        self.assertEqual(report.max_target_skip_run_frames, 2)

    def test_build_report_includes_profile_mapping(self) -> None:
        report = build_temporal_gate_report(
            records=[_record(index=0, target_gt_count=1), _record(index=1, target_gt_count=0)],
            profiles=[
                TemporalGateProfile(name="process_all", mode="all"),
                TemporalGateProfile(name="fixed_skip_2", mode="fixed_interval", interval=2),
            ],
            dataset_config="configs/datasets/sample.yaml",
            experiment_name="sample",
            target_classes=["person"],
        )

        self.assertEqual(report.frame_count, 2)
        self.assertEqual(report.target_frame_count, 1)
        self.assertEqual(report.target_gt_count, 1)
        self.assertEqual(tuple(report.profiles.keys()), ("process_all", "fixed_skip_2"))
        self.assertEqual(report.target_classes, ("person",))


def _record(
    index: int,
    target_gt_count: int,
    scene_delta_mean: float = 0.0,
) -> TemporalFrameRecord:
    return TemporalFrameRecord(
        camera_id="cam",
        frame_id=index,
        timestamp=float(index),
        frame_index=index,
        has_target=target_gt_count > 0,
        target_gt_count=target_gt_count,
        scene_delta_mean=scene_delta_mean,
        scene_delta_p95=scene_delta_mean,
    )


if __name__ == "__main__":
    unittest.main()
