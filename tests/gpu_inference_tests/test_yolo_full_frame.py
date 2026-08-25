from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common import FramePacket, FrameSize
from gpu_inference.yolo_full_frame import (
    FullFrameYoloRunner,
    YoloConfig,
    YoloOutputPaths,
    write_detection_jsonl,
    write_metrics_json,
)


class FakeFrame:
    shape = (48, 64, 3)


class FakeBoxes:
    xyxy = [[1, 2, 11, 22], [3, 4, 13, 24]]
    conf = [0.9, 0.7]
    cls = [0, 2]


class FakeResult:
    boxes = FakeBoxes()
    names = {0: "person", 2: "truck"}


class FakeModel:
    def __init__(self) -> None:
        self.calls = []

    def predict(self, frame, imgsz: int, conf: float, iou: float, verbose: bool):
        self.calls.append(
            {
                "frame": frame,
                "imgsz": imgsz,
                "conf": conf,
                "iou": iou,
                "verbose": verbose,
            }
        )
        return [FakeResult()]


class FullFrameYoloRunnerTest(unittest.TestCase):
    def test_runner_converts_yolo_results_and_records_metrics(self) -> None:
        model = FakeModel()
        runner = FullFrameYoloRunner(
            model_path="fake.pt",
            image_size=320,
            confidence_threshold=0.3,
            iou_threshold=0.5,
            classes=("person",),
            model=model,
        )

        detections = runner.run([_packet(frame_id=7)])

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].camera_id, "cam_test")
        self.assertEqual(detections[0].frame_id, 7)
        self.assertEqual(detections[0].class_name, "person")
        self.assertEqual(detections[0].bbox_xyxy, [1.0, 2.0, 11.0, 22.0])
        self.assertEqual(detections[0].source, "full_frame_yolo")
        self.assertIsNone(detections[0].roi_id)
        self.assertEqual(model.calls[0]["imgsz"], 320)
        self.assertEqual(runner.last_metrics.frame_count, 1)
        self.assertEqual(runner.last_metrics.yolo_call_count, 1)
        self.assertEqual(runner.last_metrics.yolo_input_pixel_area, 64 * 48)
        self.assertEqual(runner.last_metrics.detection_count, 1)

    def test_config_parsing_uses_yolo_and_output_sections(self) -> None:
        config = {
            "yolo": {
                "model": "custom.pt",
                "image_size": 512,
                "confidence_threshold": 0.4,
                "iou_threshold": 0.6,
                "classes": ["car"],
            },
            "outputs": {
                "full_frame_detections": "tmp/full.jsonl",
                "full_frame_metrics": "tmp/full.json",
            },
        }

        yolo_config = YoloConfig.from_mapping(config)
        output_paths = YoloOutputPaths.from_mapping(config)

        self.assertEqual(yolo_config.model, "custom.pt")
        self.assertEqual(yolo_config.classes, ("car",))
        self.assertEqual(output_paths.full_frame_detections, Path("tmp/full.jsonl"))
        self.assertEqual(output_paths.full_frame_metrics, Path("tmp/full.json"))

    def test_writers_create_json_outputs(self) -> None:
        model = FakeModel()
        runner = FullFrameYoloRunner("fake.pt", classes=("person",), model=model)
        detections = runner.run([_packet(frame_id=1)])

        with tempfile.TemporaryDirectory() as temp_dir:
            detection_path = Path(temp_dir) / "detections.jsonl"
            metrics_path = Path(temp_dir) / "metrics.json"

            write_detection_jsonl(detections, detection_path)
            write_metrics_json(runner.last_metrics, metrics_path)

            detection_record = json.loads(detection_path.read_text(encoding="utf-8").strip())
            metric_record = json.loads(metrics_path.read_text(encoding="utf-8"))

        self.assertEqual(detection_record["source"], "full_frame_yolo")
        self.assertEqual(metric_record["frame_count"], 1)
        self.assertIn("average_latency_ms", metric_record)


def _packet(frame_id: int) -> FramePacket:
    return FramePacket(
        camera_id="cam_test",
        frame_id=frame_id,
        timestamp=frame_id / 30.0,
        frame=FakeFrame(),
        original_size=FrameSize(width=64, height=48),
    )


if __name__ == "__main__":
    unittest.main()
