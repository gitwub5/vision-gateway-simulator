from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common import Detection
from common.io import read_json, read_jsonl, write_json, write_jsonl
from common.records import format_ratio, frame_key, group_by_frame
from experiments.runner_common import (
    StageTimer,
    file_provenance,
    make_prefixed_run_id,
    read_manifest,
)


class CommonIoTest(unittest.TestCase):
    def test_json_and_jsonl_helpers_round_trip(self) -> None:
        detection = Detection(
            camera_id="cam_01",
            frame_id=7,
            class_id=0,
            class_name="person",
            confidence=0.9,
            bbox_xyxy=[1, 2, 3, 4],
            source="test",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_path = root / "manifest.json"
            jsonl_path = root / "detections.jsonl"

            write_json({"ok": True}, json_path)
            write_jsonl([detection], jsonl_path)

            self.assertEqual(read_json(json_path), {"ok": True})
            self.assertEqual(read_jsonl(jsonl_path)[0]["frame_id"], 7)
            self.assertEqual(json.loads(jsonl_path.read_text(encoding="utf-8"))["source"], "test")


class CommonRecordTest(unittest.TestCase):
    def test_frame_grouping_and_ratio_formatting(self) -> None:
        records = [
            Detection("cam_01", 1, 0, "person", 0.9, [1, 2, 3, 4], "test"),
            Detection("cam_01", 1, 0, "person", 0.8, [2, 3, 4, 5], "test"),
        ]

        grouped = group_by_frame(records)

        self.assertEqual(frame_key("cam_01", 1), ("cam_01", 1))
        self.assertEqual(len(grouped[("cam_01", 1)]), 2)
        self.assertEqual(format_ratio(0.125), "0.125 (12.5%)")


class RunnerCommonTest(unittest.TestCase):
    def test_stage_timer_records_elapsed_time_and_run_id_prefix(self) -> None:
        timer = StageTimer()

        result = timer.run("stage", lambda: 42)

        self.assertEqual(result, 42)
        self.assertIn("stage", timer.stage_seconds)
        self.assertGreaterEqual(timer.stage_seconds["stage"], 0.0)
        run_id = make_prefixed_run_id(__import__("datetime").datetime(2026, 8, 7, 1, 2, 3), "sample", "e2e")
        self.assertEqual(run_id, "20260807_010203_e2e_sample")

    def test_manifest_reader_and_file_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.yaml"
            manifest_path = root / "manifest.json"
            config_path.write_text("value: 1\n", encoding="utf-8")
            write_json(
                {
                    "schema_version": 1,
                    "pipeline_type": "roi_proposal_validation",
                },
                manifest_path,
            )

            provenance = file_provenance(config_path)
            manifest = read_manifest(manifest_path, expected_pipeline_type="roi_proposal_validation")

        self.assertEqual(len(provenance["sha256"]), 64)
        self.assertEqual(manifest["schema_version"], 1)

    def test_manifest_reader_rejects_incompatible_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "manifest.json"
            write_json({"schema_version": 2, "pipeline_type": "roi_proposal_validation"}, path)
            with self.assertRaises(ValueError):
                read_manifest(path)


if __name__ == "__main__":
    unittest.main()
