from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from common import FramePacket, FrameSize, ROI, TriggerType
from roi_generator.gate import GateDecision
from roi_generator.metadata import (
    GateFrameMetadataWriter,
    ROIMetadataWriter,
    build_roi_id,
    frame_metadata_from_gate_decision,
    roi_metadata_from_gate_decision,
)


class RoiMetadataConversionTest(unittest.TestCase):
    def test_build_roi_id_is_stable_and_zero_padded(self) -> None:
        self.assertEqual(build_roi_id("cam 01", 12, 3), "cam_01_f000012_roi_003")

    def test_roi_metadata_from_gate_decision_creates_one_record_per_roi(self) -> None:
        decision = _decision(
            trigger_type=TriggerType.ROI,
            rois=[ROI(1, 2, 3, 4, score=0.5), ROI(5, 6, 7, 8, score=0.7)],
        )

        records = roi_metadata_from_gate_decision(decision)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].roi_id, "cam_01_f000042_roi_001")
        self.assertEqual(records[1].roi_id, "cam_01_f000042_roi_002")
        self.assertEqual(records[0].trigger_type, TriggerType.ROI)
        self.assertEqual(records[0].to_json_dict()["roi_xywh"], [1, 2, 3, 4])

    def test_roi_metadata_from_empty_decision_returns_empty_list(self) -> None:
        decision = _decision(trigger_type=TriggerType.FULL_FRAME, rois=[], should_run_full_frame=True)

        self.assertEqual(roi_metadata_from_gate_decision(decision), [])

    def test_frame_metadata_records_trigger_and_latency(self) -> None:
        decision = _decision(trigger_type=TriggerType.HOLD, rois=[ROI(1, 2, 3, 4)], gate_latency_ms=1.25)

        record = frame_metadata_from_gate_decision(decision)
        data = record.to_json_dict()

        self.assertEqual(data["trigger_type"], "temporal_hold")
        self.assertEqual(data["roi_count"], 1)
        self.assertFalse(data["should_run_full_frame"])
        self.assertEqual(data["gate_latency_ms"], 1.25)


class MetadataWriterTest(unittest.TestCase):
    def test_roi_metadata_writer_writes_jsonl(self) -> None:
        decision = _decision(trigger_type=TriggerType.ROI, rois=[ROI(1, 2, 3, 4)])
        records = roi_metadata_from_gate_decision(decision)

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "rule_roi.jsonl"
            writer = ROIMetadataWriter(output)
            writer.write_many(records)
            writer.write(records[0])

            lines = output.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["roi_id"], "cam_01_f000042_roi_001")
        self.assertEqual(json.loads(lines[1])["roi_id"], "cam_01_f000042_roi_001")

    def test_gate_frame_metadata_writer_writes_jsonl(self) -> None:
        record = frame_metadata_from_gate_decision(
            _decision(trigger_type=TriggerType.FULL_FRAME, rois=[], should_run_full_frame=True)
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "gate_decisions.jsonl"
            writer = GateFrameMetadataWriter(output)
            writer.write(record)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(data["trigger_type"], "full_frame")
        self.assertTrue(data["should_run_full_frame"])


class RunRuleRoiBaselineTest(unittest.TestCase):
    def test_main_writes_roi_and_frame_outputs(self) -> None:
        import experiments.run_rule_roi_baseline as runner

        packets = [
            FramePacket("cam_01", 0, 0.0, object(), FrameSize(100, 100)),
            FramePacket("cam_01", 1, 0.033, object(), FrameSize(100, 100)),
        ]

        class FakeGate:
            def __init__(self, config) -> None:
                pass

            def process(self, packet: FramePacket) -> GateDecision:
                if packet.frame_id == 0:
                    return _decision(
                        frame_id=packet.frame_id,
                        trigger_type=TriggerType.FULL_FRAME,
                        rois=[],
                        should_run_full_frame=True,
                    )
                return _decision(frame_id=packet.frame_id, trigger_type=TriggerType.ROI, rois=[ROI(1, 2, 3, 4)])

        with tempfile.TemporaryDirectory() as temp_dir:
            roi_output = Path(temp_dir) / "rule_roi.jsonl"
            frame_output = Path(temp_dir) / "gate_decisions.jsonl"
            argv = [
                "run_rule_roi_baseline.py",
                "--roi-output",
                str(roi_output),
                "--frame-output",
                str(frame_output),
            ]

            with patch.object(runner, "load_dataset_config", return_value=object()), patch.object(
                runner, "load_roi_generator_config", return_value=object()
            ), patch.object(runner, "create_dataset_stream", return_value=iter(packets)), patch.object(
                runner, "RuleBasedRoiGenerator", FakeGate
            ), patch("sys.argv", argv), redirect_stdout(StringIO()):
                runner.main()

            roi_lines = roi_output.read_text(encoding="utf-8").splitlines()
            frame_lines = frame_output.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(roi_lines), 1)
        self.assertEqual(len(frame_lines), 2)
        self.assertEqual(json.loads(roi_lines[0])["frame_id"], 1)
        self.assertEqual(json.loads(frame_lines[0])["trigger_type"], "full_frame")
        self.assertEqual(json.loads(frame_lines[1])["trigger_type"], "roi")


def _decision(
    trigger_type: TriggerType,
    rois: list[ROI],
    frame_id: int = 42,
    should_run_full_frame: bool = False,
    gate_latency_ms: float = 0.5,
) -> GateDecision:
    return GateDecision(
        camera_id="cam_01",
        frame_id=frame_id,
        timestamp=frame_id / 30.0,
        trigger_type=trigger_type,
        rois=rois,
        original_frame_size=FrameSize(100, 100),
        analysis_frame_size=FrameSize(10, 10),
        gate_latency_ms=gate_latency_ms,
        should_run_full_frame=should_run_full_frame,
    )


if __name__ == "__main__":
    unittest.main()
