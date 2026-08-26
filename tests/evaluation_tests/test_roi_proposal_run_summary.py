from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from common.io import write_json
from tools.summarize_roi_proposal_runs import render_markdown, summarize_runs


class RoiProposalRunSummaryTest(unittest.TestCase):
    def test_summarizes_compatible_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = self._write_run(root / "first", start_frame=5400, containment=0.54)
            second = self._write_run(root / "second", start_frame=5400, containment=0.64)

            summary = summarize_runs([f"baseline={first}", f"candidate={second}"])
            markdown = render_markdown(summary)

        self.assertEqual(len(summary["runs"]), 2)
        self.assertEqual(summary["runs"][1]["feedback_mode"], "actual_yolo")
        self.assertIn("| candidate |", markdown)
        self.assertIn("Tile metrics", markdown)

    def test_rejects_incompatible_dataset_segments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = self._write_run(root / "first", start_frame=5400, containment=0.54)
            second = self._write_run(root / "second", start_frame=6000, containment=0.64)

            with self.assertRaises(ValueError):
                summarize_runs([f"baseline={first}", f"candidate={second}"])

    def _write_run(self, root: Path, start_frame: int, containment: float) -> Path:
        write_json(
            {
                "schema_version": 1,
                "pipeline_type": "roi_proposal_validation",
                "run_id": root.name,
                "inputs": {
                    "diagnostics_level": "tile_trace",
                    "reference_feedback_mode": "actual_yolo",
                },
                "provenance": {
                    "resolved": {
                        "dataset": {
                            "input_path": "data/physicalai/row0709",
                            "camera_id": "Camera_0002",
                            "start_frame": start_frame,
                            "effective_frame_limit": 600,
                        },
                        "target_classes": ["person"],
                    }
                },
            },
            root / "manifest.json",
        )
        write_json(
            {
                "schema_version": 1,
                "target_gt_roi_containment": containment,
                "missed_gt_count": 100,
                "object_size_buckets": {
                    "small": {"containment": containment - 0.02, "missed_gt_count": 80}
                },
                "average_roi_count_per_frame": 2.5,
                "average_selected_tile_count_per_frame": 12.0,
                "average_tensor_batch_cost_per_frame": 250000.0,
                "effective_input_area_reduction": 0.84,
                "fallback_frame_count": 20,
                "false_roi_rate": 0.3,
                "tile_metrics_available": True,
            },
            root / "reports" / "roi_proposal_report.json",
        )
        return root


if __name__ == "__main__":
    unittest.main()
