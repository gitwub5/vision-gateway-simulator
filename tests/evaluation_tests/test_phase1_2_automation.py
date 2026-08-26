from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.run_validation_matrix import (
    build_matrix_plan,
    execute_matrix,
    load_matrix_experiment,
    load_profile_registry,
)
from tools.classify_boundary_misses import classify_boundary_misses
from visualization.artifacts import RoiRunArtifacts


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Phase12AutomationTest(unittest.TestCase):
    def test_matrix_resolves_registry_and_experiment_owned_diagnostics(self) -> None:
        experiment_path = PROJECT_ROOT / "configs" / "experiments" / "phase1_2_baselines.yaml"
        registry_path = PROJECT_ROOT / "configs" / "roi_generator" / "profiles.yaml"
        experiment = load_matrix_experiment(experiment_path)
        registry = load_profile_registry(registry_path)

        plan = build_matrix_plan(
            experiment=experiment,
            registry=registry,
            run_output_root="outputs/test",
            run_suffix="test",
        )

        self.assertEqual(experiment.diagnostics_level, "tile_trace")
        self.assertEqual([item.profile for item in plan], list(experiment.profiles))
        self.assertIn("--diagnostics-level", plan[0].command)
        diagnostics_index = plan[0].command.index("--diagnostics-level")
        self.assertEqual(plan[0].command[diagnostics_index + 1], "tile_trace")
        feedback_run = next(item for item in plan if item.profile == "feedback_actual_yolo")
        feedback_index = feedback_run.command.index("--reference-feedback-source")
        self.assertEqual(feedback_run.command[feedback_index + 1], "full_frame_yolo")

    def test_matrix_rejects_disabled_profile_and_writes_dry_run_manifest(self) -> None:
        experiment_path = PROJECT_ROOT / "configs" / "experiments" / "phase1_2_baselines.yaml"
        registry_path = PROJECT_ROOT / "configs" / "roi_generator" / "profiles.yaml"
        experiment = load_matrix_experiment(experiment_path)
        registry = load_profile_registry(registry_path)
        with self.assertRaises(ValueError):
            build_matrix_plan(
                experiment=replace(experiment, profiles=("hybrid_cost",)),
                registry=registry,
                run_output_root="outputs/test",
                run_suffix="test",
            )
        mismatched_registry = dict(registry)
        mismatched_registry["tile_baseline"] = replace(
            registry["tile_baseline"],
            reference_feedback_source="ground_truth",
        )
        with self.assertRaises(ValueError):
            build_matrix_plan(
                experiment=replace(experiment, profiles=("tile_baseline",)),
                registry=mismatched_registry,
                run_output_root="outputs/test",
                run_suffix="test",
            )

        plan = build_matrix_plan(
            experiment=replace(experiment, profiles=("tile_baseline",)),
            registry=registry,
            run_output_root="outputs/test",
            run_suffix="test",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            matrix_root = Path(temp_dir) / "matrix"
            execute_matrix(
                plan=plan,
                matrix_root=matrix_root,
                experiment_path=experiment_path,
                registry_path=registry_path,
                experiment=experiment,
                dry_run=True,
            )
            manifest = json.loads((matrix_root / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["dry_run"])
        self.assertEqual(manifest["runs"][0]["status"], "planned")

    def test_boundary_taxonomy_classifies_three_initial_categories(self) -> None:
        run = self._run_artifacts()

        result = classify_boundary_misses(run)

        self.assertEqual(
            [record.miss_type for record in result.records],
            [
                "margin_insufficient",
                "adjacent_tile_not_selected",
                "signal_missing",
            ],
        )

    def test_boundary_taxonomy_requires_true_tile_trace(self) -> None:
        with self.assertRaises(ValueError):
            classify_boundary_misses(replace(self._run_artifacts(), tile_trace_available=False))

    @staticmethod
    def _run_artifacts() -> RoiRunArtifacts:
        manifest = {
            "run_id": "taxonomy_test",
            "provenance": {
                "resolved": {
                    "dataset": {
                        "input_path": "data/test.mp4",
                        "camera_id": "cam",
                        "start_frame": 1,
                        "effective_frame_limit": 3,
                    },
                    "target_classes": ["person"],
                }
            },
        }
        ground_truth = {
            ("cam", 1): [{"annotation_id": 1, "class_name": "person", "bbox_xyxy": [1, 1, 11, 10]}],
            ("cam", 2): [{"annotation_id": 2, "class_name": "person", "bbox_xyxy": [8, 0, 22, 10]}],
            ("cam", 3): [{"annotation_id": 3, "class_name": "person", "bbox_xyxy": [20, 0, 30, 10]}],
        }
        rois = {
            ("cam", 1): [{"roi_xywh": [0, 0, 10, 10]}],
            ("cam", 2): [{"roi_xywh": [0, 0, 10, 10]}],
        }
        selected = {
            "tile_id": 0,
            "row": 0,
            "col": 0,
            "bbox_xywh": [0, 0, 10, 10],
            "selected": True,
            "motion_density": 0.1,
        }
        unselected = {
            "tile_id": 1,
            "row": 0,
            "col": 1,
            "bbox_xywh": [10, 0, 10, 10],
            "selected": False,
            "motion_density": 0.005,
        }
        signal_missing_tile = {
            "tile_id": 2,
            "row": 0,
            "col": 2,
            "bbox_xywh": [20, 0, 10, 10],
            "selected": False,
            "motion_density": 0.0,
        }
        return RoiRunArtifacts(
            label="test",
            root=Path("outputs/test"),
            manifest=manifest,
            rois_by_frame=rois,
            frames_by_frame={
                ("cam", 1): {"should_run_full_frame": False},
                ("cam", 2): {"should_run_full_frame": False},
                ("cam", 3): {"should_run_full_frame": False},
            },
            tiles_by_frame={
                ("cam", 1): [selected, unselected],
                ("cam", 2): [selected, unselected],
                ("cam", 3): [selected, unselected, signal_missing_tile],
            },
            ground_truth_by_frame=ground_truth,
            feedback_by_frame={},
            tile_trace_available=True,
        )


if __name__ == "__main__":
    unittest.main()
