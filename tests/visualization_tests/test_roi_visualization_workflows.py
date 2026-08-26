from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common import FramePacket, FrameSize
from common.io import write_json
from visualization.artifacts import ensure_compatible_runs, load_roi_run
from visualization.frame_selection import select_frame_keys
from visualization.roi_debug_renderer import debug_panel_kind
from visualization.roi_proposal_renderer import render_roi_run_review


class FakeFrame:
    shape = (48, 64, 3)

    def copy(self):
        return FakeFrame()


class FakeCv2:
    FONT_HERSHEY_SIMPLEX = 0
    LINE_AA = 16

    def __init__(self) -> None:
        self.saved_paths: list[str] = []

    def rectangle(self, *args):
        return None

    def putText(self, *args):
        return None

    def imwrite(self, path, image):
        self.saved_paths.append(path)
        return True


class RoiVisualizationWorkflowTest(unittest.TestCase):
    def test_artifact_loader_and_disagreement_selection_use_camera_frame_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = load_roi_run(self._write_run(root / "baseline", contains=True), "baseline")
            candidate = load_roi_run(self._write_run(root / "candidate", contains=False), "candidate")

            compatibility = ensure_compatible_runs([baseline, candidate])
            selected = select_frame_keys([baseline, candidate], "disagreement", max_frames=5)

        self.assertEqual(compatibility["start_frame"], 1)
        self.assertEqual(selected, [("cam_test", 1)])
        self.assertTrue(baseline.tile_trace_available)

    def test_incompatible_run_segments_fail_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = load_roi_run(self._write_run(root / "baseline", contains=True), "baseline")
            candidate_root = self._write_run(root / "candidate", contains=True, start_frame=2)
            candidate = load_roi_run(candidate_root, "candidate")

            with self.assertRaises(ValueError):
                ensure_compatible_runs([baseline, candidate])

    def test_single_run_review_writes_separate_views_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run = load_roi_run(self._write_run(root / "run", contains=False), "run")
            output = root / "review"
            fake_cv2 = FakeCv2()

            import visualization.roi_proposal_renderer as renderer

            original_loader = renderer.load_shared_dependencies
            renderer.load_shared_dependencies = lambda: (fake_cv2, object())
            try:
                summary = render_roi_run_review(
                    run=run,
                    frames=[self._packet()],
                    output_root=output,
                    selection_preset="missed",
                    max_frames=1,
                )
            finally:
                renderer.load_shared_dependencies = original_loader

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(summary.rendered_by_view["overlay"], 1)
        self.assertEqual(summary.rendered_by_view["containment"], 1)
        self.assertEqual(summary.rendered_by_view["failures"], 1)
        self.assertEqual(manifest["source_run_id"], "run")
        self.assertTrue(any("/roi_overlay/" in path for path in fake_cv2.saved_paths))

    def test_debug_panel_kind_is_policy_aware(self) -> None:
        self.assertEqual(debug_panel_kind("tile_mask"), "tile")
        self.assertEqual(debug_panel_kind("hybrid_component_tile"), "tile")
        self.assertEqual(debug_panel_kind("component_bbox"), "component")

    def _write_run(
        self,
        root: Path,
        contains: bool,
        start_frame: int = 1,
    ) -> Path:
        write_json(
            {
                "schema_version": 1,
                "pipeline_type": "roi_proposal_validation",
                "run_id": root.name,
                "inputs": {"dataset_config": "configs/datasets/base/smoke.yaml"},
                "provenance": {
                    "resolved": {
                        "dataset": {
                            "input_path": "data/test.mp4",
                            "camera_id": "cam_test",
                            "start_frame": start_frame,
                            "effective_frame_limit": 1,
                        },
                        "target_classes": ["person"],
                    }
                },
                "outputs": {},
            },
            root / "manifest.json",
        )
        roi = [0, 0, 20, 20] if contains else [30, 30, 10, 10]
        self._write_jsonl(
            root / "roi_metadata" / "rule_roi.jsonl",
            [{"camera_id": "cam_test", "frame_id": 1, "roi_xywh": roi}],
        )
        self._write_jsonl(
            root / "roi_metadata" / "gate_decisions.jsonl",
            [{"camera_id": "cam_test", "frame_id": 1, "selected_tile_count": 1}],
        )
        self._write_jsonl(
            root / "roi_metadata" / "tile_metadata.jsonl",
            [{
                "camera_id": "cam_test",
                "frame_id": 1,
                "bbox_xywh": [0, 0, 16, 12],
                "selected": True,
            }],
        )
        self._write_jsonl(
            root / "annotations" / "ground_truth.jsonl",
            [{
                "camera_id": "cam_test",
                "frame_id": 1,
                "bbox_xyxy": [1, 1, 10, 10],
                "class_name": "person",
            }],
        )
        return root

    @staticmethod
    def _write_jsonl(path: Path, records: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )

    @staticmethod
    def _packet() -> FramePacket:
        return FramePacket(
            camera_id="cam_test",
            frame_id=1,
            timestamp=0.0,
            frame=FakeFrame(),
            original_size=FrameSize(width=64, height=48),
        )


if __name__ == "__main__":
    unittest.main()
