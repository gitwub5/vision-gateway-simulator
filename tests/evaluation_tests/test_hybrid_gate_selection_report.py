from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from common.io import write_json
from evaluation.reports.hybrid_gate_selection import build_hybrid_gate_selection_report


class HybridGateSelectionReportTest(unittest.TestCase):
    def test_selects_tracker_hybrid_when_recall_and_reduction_are_high(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            static_path = root / "static.json"
            tracker_path = root / "tracker.json"
            lightweight_path = root / "lightweight.json"
            temporal_path = root / "temporal.json"
            write_json(_summary("sample", {"top": _static_profile(0.80, 1.0, 0.70)}), static_path)
            write_json(_summary("sample", {"refresh": _tracker_profile(0.97, 0.75, 4.0)}), tracker_path)
            write_json(_summary("sample", {"hybrid": _lightweight_profile(0.50, 0.80, 0.45)}), lightweight_path)
            write_json(_summary("sample", {"process_all": _temporal_profile(1.0, 0.0)}), temporal_path)

            report = build_hybrid_gate_selection_report(
                static_summary_path=static_path,
                tracker_summary_path=tracker_path,
                lightweight_summary_path=lightweight_path,
                temporal_summary_path=temporal_path,
            )

        recommendation = report.recommendations["sample"]
        self.assertEqual(
            recommendation.selected_candidate,
            "static_zone_prior + tracker_memory + temporal_refresh_guard",
        )
        self.assertEqual(recommendation.confidence, "high")

    def test_marks_traffic_as_new_probe_even_when_static_center_is_strong(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            static_path = root / "static.json"
            tracker_path = root / "tracker.json"
            lightweight_path = root / "lightweight.json"
            temporal_path = root / "temporal.json"
            name = "phase1_3_traffic_ua_detrac_mvi_39361"
            write_json(_summary(name, {"top": _static_profile(0.44, 1.0, 0.72)}), static_path)
            write_json(_summary(name, {"refresh": _tracker_profile(0.75, 0.40, 4.0)}), tracker_path)
            write_json(_summary(name, {"hybrid": _lightweight_profile(0.07, 0.82, 0.44)}), lightweight_path)
            write_json(_summary(name, {"process_all": _temporal_profile(1.0, 0.0)}), temporal_path)

            report = build_hybrid_gate_selection_report(
                static_summary_path=static_path,
                tracker_summary_path=tracker_path,
                lightweight_summary_path=lightweight_path,
                temporal_summary_path=temporal_path,
            )

        recommendation = report.recommendations[name]
        self.assertEqual(recommendation.selected_candidate, "lane_or_scale_prior + velocity_tracker")
        self.assertEqual(recommendation.confidence, "needs_new_probe")


def _summary(experiment_name: str, profiles: dict[str, dict[str, float]]) -> dict[str, object]:
    return {"schema_version": 1, "runs": [{"experiment_name": experiment_name, "profiles": profiles}]}


def _static_profile(bbox_recall: float, center_recall: float, reduction: float) -> dict[str, float]:
    return {
        "bbox_gt_recall": bbox_recall,
        "center_gt_recall": center_recall,
        "input_area_reduction": reduction,
    }


def _tracker_profile(recall: float, reduction: float, roi_count: float) -> dict[str, float]:
    return {
        "target_gt_recall": recall,
        "effective_input_area_reduction": reduction,
        "memory_frame_target_gt_recall": recall,
        "average_memory_roi_count_per_memory_frame": roi_count,
    }


def _lightweight_profile(bbox_recall: float, center_recall: float, reduction: float) -> dict[str, float]:
    return {
        "bbox_gt_recall": bbox_recall,
        "center_gt_recall": center_recall,
        "input_area_reduction": reduction,
    }


def _temporal_profile(recall: float, reduction: float) -> dict[str, float]:
    return {
        "target_gt_recall": recall,
        "target_frame_recall": recall,
        "detector_call_reduction": reduction,
    }


if __name__ == "__main__":
    unittest.main()
