from __future__ import annotations

import unittest

from common import Detection, FramePacket, FrameSize, GroundTruthAnnotation, ROI, ROIMetadata, TriggerType
from visualization.renderer import (
    VisualizationSummary,
    find_missed_ground_truth_annotations,
    find_missed_reference_detections,
    render_visualizations,
)


class FakeFrame:
    shape = (48, 64, 3)

    def __init__(self, name: str = "frame") -> None:
        self.name = name

    def copy(self):
        return FakeFrame(f"{self.name}_copy")


class FakeCv2:
    FONT_HERSHEY_SIMPLEX = 0
    LINE_AA = 16

    def __init__(self) -> None:
        self.saved_paths = []
        self.rectangles = []
        self.labels = []

    def rectangle(self, canvas, start, end, color, thickness):
        self.rectangles.append((start, end, color, thickness))

    def putText(self, canvas, text, origin, font, scale, color, thickness, line_type):
        self.labels.append(text)

    def imwrite(self, path, image):
        self.saved_paths.append(path)
        return True


class FakeNp:
    def concatenate(self, frames, axis):
        return FakeFrame("comparison")


class VisualizationTest(unittest.TestCase):
    def test_find_missed_reference_detections(self) -> None:
        reference = [_detection("full_frame_yolo", [0, 0, 10, 10])]
        matched = [_detection("roi_yolo", [1, 1, 11, 11], roi_id="roi_001")]
        missed = [_detection("roi_yolo", [30, 30, 40, 40], roi_id="roi_002")]

        self.assertEqual(find_missed_reference_detections(reference, matched), [])
        self.assertEqual(find_missed_reference_detections(reference, missed), reference)

    def test_find_missed_ground_truth_annotations(self) -> None:
        ground_truth = [_gt_annotation([0, 0, 10, 10])]
        matched = [_detection("roi_yolo", [1, 1, 11, 11], roi_id="roi_001")]
        missed = [_detection("roi_yolo", [30, 30, 40, 40], roi_id="roi_002")]

        self.assertEqual(find_missed_ground_truth_annotations(ground_truth, matched), [])
        self.assertEqual(find_missed_ground_truth_annotations(ground_truth, missed), ground_truth)

    def test_render_visualizations_writes_overlay_comparison_and_failure(self) -> None:
        fake_cv2 = FakeCv2()
        fake_np = FakeNp()

        import visualization.renderer as renderer

        original_loader = renderer._load_dependencies
        renderer._load_dependencies = lambda: (fake_cv2, fake_np)
        try:
            summary = render_visualizations(
                frames=[_packet()],
                roi_records=[_roi_record(ROI(0, 0, 10, 10))],
                full_frame_detections=[_detection("full_frame_yolo", [20, 20, 30, 30])],
                roi_detections=[_detection("roi_yolo", [1, 1, 8, 8], roi_id="roi_001")],
                ground_truth=[_gt_annotation([20, 20, 30, 30])],
                output_root="outputs/visualizations/test",
            )
        finally:
            renderer._load_dependencies = original_loader

        self.assertEqual(summary, VisualizationSummary(1, 1, 1, 1))
        self.assertEqual(len(fake_cv2.saved_paths), 3)
        self.assertTrue(any("roi_overlay" in path for path in fake_cv2.saved_paths))
        self.assertTrue(any("comparison" in path for path in fake_cv2.saved_paths))
        self.assertTrue(any("failures" in path for path in fake_cv2.saved_paths))


def _packet() -> FramePacket:
    return FramePacket(
        camera_id="cam_test",
        frame_id=1,
        timestamp=1 / 30.0,
        frame=FakeFrame(),
        original_size=FrameSize(width=64, height=48),
    )


def _roi_record(roi: ROI) -> ROIMetadata:
    return ROIMetadata(
        camera_id="cam_test",
        frame_id=1,
        timestamp=1 / 30.0,
        roi_id="roi_001",
        original_frame_size=FrameSize(width=64, height=48),
        analysis_frame_size=FrameSize(width=16, height=12),
        roi=roi,
        trigger_type=TriggerType.ROI,
    )


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


def _gt_annotation(bbox_xyxy: list[float]) -> GroundTruthAnnotation:
    return GroundTruthAnnotation(
        camera_id="cam_test",
        frame_id=1,
        class_id=0,
        class_name="person",
        bbox_xyxy=bbox_xyxy,
        annotation_id=1,
        image_id=1,
        file_name="1.jpg",
    )


if __name__ == "__main__":
    unittest.main()
