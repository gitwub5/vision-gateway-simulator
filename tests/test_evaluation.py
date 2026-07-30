from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common import Detection, FrameSize, GateFrameMetadata, GroundTruthAnnotation, ROI, ROIMetadata, TriggerType
from evaluation.comparison_report import (
    ComparisonInputs,
    build_comparison_report,
    read_detection_jsonl,
    write_report_json,
    write_report_markdown,
)
from evaluation.detection_metrics import bbox_iou, match_detections_by_iou
from evaluation.gt_report import AnnotationQuality, summarize_detector_gt, summarize_gt_roi_containment
from evaluation.roi_containment import summarize_roi_containment
from evaluation.workload_metrics import reduction_ratio


class EvaluationMetricsTest(unittest.TestCase):
    def test_bbox_iou_and_detection_matching(self) -> None:
        reference = [_detection("full_frame_yolo", [0, 0, 10, 10])]
        candidate = [_detection("roi_yolo", [1, 1, 11, 11], roi_id="roi_001")]

        self.assertGreater(bbox_iou(reference[0].bbox_xyxy, candidate[0].bbox_xyxy), 0.5)
        summary = match_detections_by_iou(reference, candidate, iou_threshold=0.5)

        self.assertEqual(summary.matched_detection_count, 1)
        self.assertEqual(summary.pseudo_recall, 1.0)

    def test_roi_containment_summary(self) -> None:
        reference = [_detection("full_frame_yolo", [2, 2, 8, 8])]
        rois = [_roi_record(ROI(0, 0, 10, 10))]
        frames = [_frame_record()]

        summary = summarize_roi_containment(reference, rois, frames)

        self.assertEqual(summary.contained_detection_count, 1)
        self.assertEqual(summary.containment_rate, 1.0)
        self.assertEqual(summary.average_roi_count, 1.0)
        self.assertEqual(summary.average_roi_area_ratio, 0.01)

    def test_reduction_ratio(self) -> None:
        self.assertEqual(reduction_ratio(100, 40), 0.6)
        self.assertEqual(reduction_ratio(100, 120), -0.2)
        self.assertEqual(reduction_ratio(0, 40), 0.0)

    def test_gt_detector_and_roi_summaries(self) -> None:
        ground_truth = [
            _gt_annotation("person", [0, 0, 10, 10]),
            _gt_annotation("Car", [30, 30, 50, 50], annotation_id=2),
        ]
        detections = [
            _detection("roi_yolo", [0, 0, 10, 10]),
            _detection("roi_yolo", [1, 1, 9, 9]),
        ]
        rois = [_roi_record(ROI(0, 0, 12, 12)), _roi_record(ROI(70, 70, 10, 10))]

        detector_summary = summarize_detector_gt("roi_yolo", ground_truth, detections)
        roi_summary = summarize_gt_roi_containment(ground_truth, rois)

        self.assertEqual(detector_summary.matched_gt_count, 1)
        self.assertEqual(detector_summary.missed_gt_count, 1)
        self.assertEqual(detector_summary.duplicate_detection_count, 1)
        self.assertEqual(detector_summary.class_recall["person"], 1.0)
        self.assertEqual(detector_summary.class_recall["Car"], 0.0)
        self.assertEqual(roi_summary.contained_gt_count, 1)
        self.assertEqual(roi_summary.false_roi_count, 1)

    def test_annotation_quality_from_mapping(self) -> None:
        quality = AnnotationQuality.from_mapping(
            {
                "completeness": "partial",
                "expected_exhaustive": False,
                "notes": ["visible objects may be unlabeled"],
                "unreliable_metrics": ["false_roi_rate"],
            }
        )

        self.assertEqual(quality.completeness, "partial")
        self.assertFalse(quality.expected_exhaustive)
        self.assertEqual(quality.notes, ("visible objects may be unlabeled",))
        self.assertEqual(quality.unreliable_metrics, ("false_roi_rate",))


class ComparisonReportTest(unittest.TestCase):
    def test_build_and_write_comparison_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inputs = ComparisonInputs(
                full_frame_detections=root / "full_frame.jsonl",
                roi_detections=root / "roi_yolo.jsonl",
                full_frame_metrics=root / "full_frame_metrics.json",
                roi_metrics=root / "roi_yolo_metrics.json",
                roi_metadata=root / "rule_roi.jsonl",
                frame_metadata=root / "gate_decisions.jsonl",
                report_json=root / "comparison_report.json",
                report_markdown=root / "comparison_report.md",
            )
            _write_jsonl(inputs.full_frame_detections, [_detection("full_frame_yolo", [2, 2, 8, 8])])
            _write_jsonl(inputs.roi_detections, [_detection("roi_yolo", [2, 2, 8, 8], roi_id="roi_001")])
            inputs.full_frame_metrics.write_text(
                json.dumps(
                    {
                        "yolo_call_count": 10,
                        "yolo_input_pixel_area": 1000,
                        "average_latency_ms": 20.0,
                    }
                ),
                encoding="utf-8",
            )
            inputs.roi_metrics.write_text(
                json.dumps(
                    {
                        "yolo_call_count": 4,
                        "yolo_input_pixel_area": 300,
                        "average_latency_ms": 8.0,
                    }
                ),
                encoding="utf-8",
            )
            _write_jsonl(inputs.roi_metadata, [_roi_record(ROI(0, 0, 10, 10))])
            _write_jsonl(inputs.frame_metadata, [_frame_record()])

            report = build_comparison_report(inputs)
            write_report_json(report, inputs.report_json)
            write_report_markdown(report, inputs.report_markdown)

            json_report = json.loads(inputs.report_json.read_text(encoding="utf-8"))
            markdown_report = inputs.report_markdown.read_text(encoding="utf-8")

        self.assertEqual(json_report["detection"]["pseudo_recall"], 1.0)
        self.assertEqual(json_report["workload"]["input_pixel_area_reduction"], 0.7)
        self.assertIn("Phase 1 Comparison Report", markdown_report)

    def test_detection_reader_round_trips_detection_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "detections.jsonl"
            _write_jsonl(path, [_detection("roi_yolo", [1, 2, 3, 4], roi_id="roi_001")])

            detections = read_detection_jsonl(path)

        self.assertEqual(detections[0].roi_id, "roi_001")
        self.assertEqual(detections[0].bbox_xyxy, [1.0, 2.0, 3.0, 4.0])


def _write_jsonl(path: Path, records: list) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record.to_json_dict()) + "\n")


def _detection(source: str, bbox_xyxy: list[float], roi_id: str | None = None) -> Detection:
    return Detection(
        camera_id="cam_test",
        frame_id=1,
        class_id=0,
        class_name="person",
        confidence=0.9,
        bbox_xyxy=bbox_xyxy,
        source=source,
        roi_id=roi_id,
    )


def _gt_annotation(
    class_name: str,
    bbox_xyxy: list[float],
    annotation_id: int = 1,
) -> GroundTruthAnnotation:
    return GroundTruthAnnotation(
        camera_id="cam_test",
        frame_id=1,
        class_id=0,
        class_name=class_name,
        bbox_xyxy=bbox_xyxy,
        annotation_id=annotation_id,
        image_id=1,
        file_name="1.jpg",
    )


def _roi_record(roi: ROI) -> ROIMetadata:
    return ROIMetadata(
        camera_id="cam_test",
        frame_id=1,
        timestamp=1 / 30.0,
        roi_id="roi_001",
        original_frame_size=FrameSize(width=100, height=100),
        analysis_frame_size=FrameSize(width=10, height=10),
        roi=roi,
        trigger_type=TriggerType.ROI,
    )


def _frame_record() -> GateFrameMetadata:
    return GateFrameMetadata(
        camera_id="cam_test",
        frame_id=1,
        timestamp=1 / 30.0,
        trigger_type=TriggerType.ROI,
        roi_count=1,
        should_run_full_frame=False,
        gate_latency_ms=0.5,
        original_frame_size=FrameSize(width=100, height=100),
        analysis_frame_size=FrameSize(width=10, height=10),
    )


if __name__ == "__main__":
    unittest.main()
