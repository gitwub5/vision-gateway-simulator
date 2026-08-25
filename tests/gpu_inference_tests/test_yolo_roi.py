from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common import FramePacket, FrameSize, GateFrameMetadata, ROI, ROIMetadata, TriggerType
from gpu_inference.yolo_roi import (
    FULL_FRAME_CHECK_SOURCE,
    ROI_YOLO_SOURCE,
    RoiYoloRunner,
    clipped_roi_area,
    crop_frame,
    read_gate_frame_metadata_jsonl,
    read_roi_metadata_jsonl,
    write_roi_metrics_json,
)


class FakeCrop:
    def __init__(self, key) -> None:
        self.key = key


class FakeFrame:
    shape = (48, 64, 3)

    def __getitem__(self, key):
        return FakeCrop(key)


class FakeBoxes:
    xyxy = [[1, 2, 11, 22], [3, 4, 13, 24]]
    conf = [0.9, 0.8]
    cls = [0, 2]


class FakeResult:
    boxes = FakeBoxes()
    names = {0: "person", 2: "truck"}


class FakeModel:
    def __init__(self) -> None:
        self.calls = []

    def predict(self, frame, imgsz: int, conf: float, iou: float, verbose: bool):
        self.calls.append(frame)
        return [FakeResult()]


class RoiYoloRunnerTest(unittest.TestCase):
    def test_runner_crops_restores_coordinates_and_merges_full_frame_checks(self) -> None:
        model = FakeModel()
        runner = RoiYoloRunner(
            model_path="fake.pt",
            image_size=320,
            confidence_threshold=0.3,
            iou_threshold=0.5,
            classes=("person",),
            model=model,
        )

        detections = runner.run(
            frames=[_packet(frame_id=7)],
            roi_records=[_roi_record(frame_id=7, roi=ROI(10, 20, 30, 40))],
            frame_records=[_frame_record(frame_id=7, should_run_full_frame=True)],
        )

        self.assertEqual(len(detections), 2)
        self.assertEqual(detections[0].source, FULL_FRAME_CHECK_SOURCE)
        self.assertEqual(detections[0].bbox_xyxy, [1.0, 2.0, 11.0, 22.0])
        self.assertIsNone(detections[0].roi_id)
        self.assertEqual(detections[1].source, ROI_YOLO_SOURCE)
        self.assertEqual(detections[1].bbox_xyxy, [11.0, 22.0, 21.0, 42.0])
        self.assertEqual(detections[1].roi_id, "cam_test_f000007_roi_001")
        self.assertEqual(runner.last_metrics.frame_count, 1)
        self.assertEqual(runner.last_metrics.full_frame_check_call_count, 1)
        self.assertEqual(runner.last_metrics.roi_yolo_call_count, 1)
        self.assertEqual(runner.last_metrics.yolo_call_count, 2)
        self.assertEqual(runner.last_metrics.roi_input_pixel_area, 30 * 28)
        self.assertEqual(runner.last_metrics.full_frame_input_pixel_area, 64 * 48)
        self.assertIsInstance(model.calls[1], FakeCrop)

    def test_crop_frame_clips_to_frame_boundary(self) -> None:
        crop = crop_frame(_packet(frame_id=1), ROI(x=60, y=40, w=20, h=20))

        self.assertEqual(crop.key, (slice(40, 48, None), slice(60, 64, None)))

    def test_metrics_use_clipped_roi_area(self) -> None:
        model = FakeModel()
        runner = RoiYoloRunner("fake.pt", classes=("person",), model=model)

        runner.run([_packet(frame_id=1)], [_roi_record(frame_id=1, roi=ROI(60, 40, 20, 20))])

        self.assertEqual(clipped_roi_area(_packet(frame_id=1), ROI(60, 40, 20, 20)), 4 * 8)
        self.assertEqual(runner.last_metrics.roi_input_pixel_area, 4 * 8)

    def test_metadata_readers_parse_jsonl_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            roi_path = Path(temp_dir) / "rule_roi.jsonl"
            frame_path = Path(temp_dir) / "gate_decisions.jsonl"
            roi_path.write_text(
                json.dumps(_roi_record(frame_id=3, roi=ROI(1, 2, 3, 4)).to_json_dict()) + "\n",
                encoding="utf-8",
            )
            frame_path.write_text(
                json.dumps(_frame_record(frame_id=3, should_run_full_frame=True).to_json_dict()) + "\n",
                encoding="utf-8",
            )

            roi_records = read_roi_metadata_jsonl(roi_path)
            frame_records = read_gate_frame_metadata_jsonl(frame_path)

        self.assertEqual(roi_records[0].roi.xywh(), [1, 2, 3, 4])
        self.assertEqual(roi_records[0].trigger_type, TriggerType.ROI)
        self.assertTrue(frame_records[0].should_run_full_frame)
        self.assertEqual(frame_records[0].trigger_type, TriggerType.FULL_FRAME)

    def test_metrics_writer_creates_json(self) -> None:
        runner = RoiYoloRunner("fake.pt", classes=("person",), model=FakeModel())
        runner.run([_packet(frame_id=1)], [_roi_record(frame_id=1, roi=ROI(1, 2, 3, 4))])

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "roi_metrics.json"
            write_roi_metrics_json(runner.last_metrics, output)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(data["roi_record_count"], 1)
        self.assertEqual(data["yolo_call_count"], 1)
        self.assertIn("average_latency_ms", data)


def _packet(frame_id: int) -> FramePacket:
    return FramePacket(
        camera_id="cam_test",
        frame_id=frame_id,
        timestamp=frame_id / 30.0,
        frame=FakeFrame(),
        original_size=FrameSize(width=64, height=48),
    )


def _roi_record(frame_id: int, roi: ROI) -> ROIMetadata:
    return ROIMetadata(
        camera_id="cam_test",
        frame_id=frame_id,
        timestamp=frame_id / 30.0,
        roi_id=f"cam_test_f{frame_id:06d}_roi_001",
        original_frame_size=FrameSize(width=64, height=48),
        analysis_frame_size=FrameSize(width=16, height=12),
        roi=roi,
        trigger_type=TriggerType.ROI,
    )


def _frame_record(frame_id: int, should_run_full_frame: bool) -> GateFrameMetadata:
    return GateFrameMetadata(
        camera_id="cam_test",
        frame_id=frame_id,
        timestamp=frame_id / 30.0,
        trigger_type=TriggerType.FULL_FRAME if should_run_full_frame else TriggerType.ROI,
        roi_count=1,
        should_run_full_frame=should_run_full_frame,
        gate_latency_ms=0.5,
        original_frame_size=FrameSize(width=64, height=48),
        analysis_frame_size=FrameSize(width=16, height=12),
    )


if __name__ == "__main__":
    unittest.main()
