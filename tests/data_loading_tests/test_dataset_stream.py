from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

from data_loader import DatasetConfig, ImageSequenceStream, VideoFrameStream, create_dataset_stream
from data_loader.dataset_stream import list_image_sequence_paths


class FakeFrame:
    shape = (24, 32, 3)


class FakeVideoCapture:
    CAP_PROP_FPS = 5
    CAP_PROP_POS_FRAMES = 1

    def __init__(self, path: str) -> None:
        self.path = path
        self.index = 0
        self.opened = True

    def isOpened(self) -> bool:
        return self.opened

    def get(self, prop: int) -> float:
        return 10.0

    def set(self, prop: int, value: int) -> None:
        self.index = int(value)

    def read(self):
        if self.index >= 3:
            return False, None
        self.index += 1
        return True, FakeFrame()

    def release(self) -> None:
        self.opened = False


class DatasetStreamTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_cv2 = sys.modules.get("cv2")
        fake_cv2 = types.SimpleNamespace(
            VideoCapture=FakeVideoCapture,
            CAP_PROP_FPS=FakeVideoCapture.CAP_PROP_FPS,
            CAP_PROP_POS_FRAMES=FakeVideoCapture.CAP_PROP_POS_FRAMES,
            imread=lambda path: FakeFrame(),
        )
        sys.modules["cv2"] = fake_cv2

    def tearDown(self) -> None:
        if self.original_cv2 is None:
            sys.modules.pop("cv2", None)
        else:
            sys.modules["cv2"] = self.original_cv2

    def test_video_stream_emits_frame_packets(self) -> None:
        stream = VideoFrameStream("sample.mp4", camera_id="cam_test", frame_limit=2)
        packets = list(stream)

        self.assertEqual(len(packets), 2)
        self.assertEqual(packets[0].camera_id, "cam_test")
        self.assertEqual(packets[0].frame_id, 0)
        self.assertEqual(packets[0].timestamp, 0.0)
        self.assertEqual(packets[0].original_size.as_list(), [32, 24])

    def test_image_sequence_stream_filters_and_emits_frame_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "0002.txt").write_text("skip", encoding="utf-8")
            (root / "0001.jpg").write_text("image", encoding="utf-8")
            (root / "0003.png").write_text("image", encoding="utf-8")

            stream = ImageSequenceStream(root, camera_id="cam_img", fps=2.0, frame_limit=1)
            packets = list(stream)

        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].camera_id, "cam_img")
        self.assertEqual(packets[0].frame_id, 0)
        self.assertEqual(packets[0].timestamp, 0.0)
        self.assertEqual(packets[0].original_size.as_list(), [32, 24])

    def test_image_sequence_paths_use_natural_numeric_sort(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ["10.jpg", "2.jpg", "1.jpg", "skip.txt"]:
                (root / name).write_text("image", encoding="utf-8")

            image_paths = list_image_sequence_paths(root)

        self.assertEqual([path.name for path in image_paths], ["1.jpg", "2.jpg", "10.jpg"])

    def test_create_dataset_stream_from_config(self) -> None:
        config = DatasetConfig(type="image_sequence", input_path=Path("."), camera_id="cam_cfg")
        stream = create_dataset_stream(config)
        self.assertIsInstance(stream, ImageSequenceStream)


if __name__ == "__main__":
    unittest.main()
