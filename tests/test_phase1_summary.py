from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common import Detection, FrameSize, GateFrameMetadata, ROI, ROIMetadata, TriggerType
from evaluation.phase1_summary import (
    profile_summaries_to_markdown,
    roi_bucket_summaries_to_markdown,
    summarize_profile_run,
    summarize_roi_count_latency,
)


class Phase1SummaryTest(unittest.TestCase):
    def test_profile_summary_reads_run_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = _write_run_fixture(Path(temp_dir))

            summary = summarize_profile_run(root)
            markdown = profile_summaries_to_markdown([summary])

        self.assertEqual(summary.run_id, "run_fixture")
        self.assertEqual(summary.yolo_call_count, 3)
        self.assertEqual(summary.full_frame_check_count, 1)
        self.assertEqual(summary.failure_case_count, 1)
        self.assertIn("Phase 1 Profile Summary", markdown)

    def test_roi_count_latency_summary_buckets_frames(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = _write_run_fixture(Path(temp_dir))

            summaries = summarize_roi_count_latency(root)
            markdown = roi_bucket_summaries_to_markdown(summaries)

        by_bucket = {summary.bucket: summary for summary in summaries}
        self.assertEqual(by_bucket["1"].frame_count, 1)
        self.assertEqual(by_bucket["2-3"].frame_count, 1)
        self.assertEqual(by_bucket["1"].roi_yolo_call_count, 1)
        self.assertEqual(by_bucket["2-3"].roi_yolo_call_count, 2)
        self.assertIn("ROI Count Latency Benchmark", markdown)


def _write_run_fixture(root: Path) -> Path:
    (root / "reports").mkdir(parents=True)
    (root / "roi_metadata").mkdir()
    (root / "detections").mkdir()
    (root / "visualizations" / "failures").mkdir(parents=True)
    (root / "visualizations" / "failures" / "cam_test_f000002_failure.jpg").write_text(
        "fake", encoding="utf-8"
    )

    _write_json(
        root / "manifest.json",
        {
            "run_id": "run_fixture",
            "experiment_name": "balanced",
            "inputs": {
                "dataset_config": "configs/dataset.test.yaml",
                "gate_config": "configs/npx_gate.profile_balanced.yaml",
                "include_full_frame_checks": True,
            },
        },
    )
    _write_json(
        root / "reports" / "comparison_report.json",
        {
            "detection": {"pseudo_recall": 0.5},
            "roi": {
                "containment_rate": 0.75,
                "average_roi_count": 1.5,
                "average_roi_area_ratio": 0.2,
            },
            "workload": {"input_pixel_area_reduction": 0.4},
            "latency": {"gate_average_latency_ms": 0.6},
        },
    )
    _write_json(
        root / "reports" / "roi_yolo_metrics.json",
        {
            "yolo_call_count": 3,
            "full_frame_check_call_count": 1,
            "average_latency_ms": 4.0,
        },
    )
    _write_json(
        root / "reports" / "full_frame_metrics.json",
        {
            "average_latency_ms": 10.0,
        },
    )

    _write_jsonl(
        root / "roi_metadata" / "rule_roi.jsonl",
        [
            _roi_record(1, "roi_1", ROI(0, 0, 10, 10)),
            _roi_record(2, "roi_2", ROI(0, 0, 10, 10)),
            _roi_record(2, "roi_3", ROI(10, 10, 10, 10)),
        ],
    )
    _write_jsonl(
        root / "roi_metadata" / "gate_decisions.jsonl",
        [
            _frame_record(1, roi_count=1, should_run_full_frame=False),
            _frame_record(2, roi_count=2, should_run_full_frame=True),
        ],
    )
    _write_jsonl(
        root / "detections" / "full_frame.jsonl",
        [
            _detection(1, [1, 1, 5, 5], "full_frame_yolo"),
            _detection(2, [30, 30, 40, 40], "full_frame_yolo"),
        ],
    )
    _write_jsonl(
        root / "detections" / "roi_yolo.jsonl",
        [
            _detection(1, [1, 1, 5, 5], "roi_yolo", roi_id="roi_1"),
        ],
    )
    return root


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_jsonl(path: Path, records: list) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record.to_json_dict()) + "\n")


def _roi_record(frame_id: int, roi_id: str, roi: ROI) -> ROIMetadata:
    return ROIMetadata(
        camera_id="cam_test",
        frame_id=frame_id,
        timestamp=frame_id / 30.0,
        roi_id=roi_id,
        original_frame_size=FrameSize(width=100, height=100),
        analysis_frame_size=FrameSize(width=10, height=10),
        roi=roi,
        trigger_type=TriggerType.ROI,
    )


def _frame_record(frame_id: int, roi_count: int, should_run_full_frame: bool) -> GateFrameMetadata:
    return GateFrameMetadata(
        camera_id="cam_test",
        frame_id=frame_id,
        timestamp=frame_id / 30.0,
        trigger_type=TriggerType.ROI,
        roi_count=roi_count,
        should_run_full_frame=should_run_full_frame,
        gate_latency_ms=0.5,
        original_frame_size=FrameSize(width=100, height=100),
        analysis_frame_size=FrameSize(width=10, height=10),
    )


def _detection(
    frame_id: int, bbox_xyxy: list[float], source: str, roi_id: str | None = None
) -> Detection:
    return Detection(
        camera_id="cam_test",
        frame_id=frame_id,
        class_id=0,
        class_name="person",
        confidence=0.9,
        bbox_xyxy=bbox_xyxy,
        source=source,
        roi_id=roi_id,
    )


if __name__ == "__main__":
    unittest.main()
