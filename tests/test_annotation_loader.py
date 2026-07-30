from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from data_loader import DatasetConfig
from data_loader.annotation_loader import ConstructionSiteStaticCameraAnnotationLoader, OdViratTinyAnnotationLoader


class AnnotationLoaderTest(unittest.TestCase):
    def test_od_virat_tiny_loader_maps_file_names_to_dataset_frame_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_root = root / "images"
            image_root.mkdir()
            for name in ["0.jpg", "1.jpg", "10.jpg", "2.jpg"]:
                (image_root / name).write_text("image", encoding="utf-8")
            annotation_path = root / "annotations.json"
            annotation_path.write_text(
                json.dumps(
                    {
                        "images": [
                            {"id": 0, "file_name": "0.jpg", "height": 100, "width": 100},
                            {"id": 1, "file_name": "1.jpg", "height": 100, "width": 100},
                            {"id": 2, "file_name": "2.jpg", "height": 100, "width": 100},
                            {"id": 10, "file_name": "10.jpg", "height": 100, "width": 100},
                        ],
                        "categories": [{"id": 4, "name": "Person"}],
                        "annotations": [
                            {"id": 5, "image_id": 10, "category_id": 4, "bbox": [1, 2, 3, 4]},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            config = DatasetConfig(type="image_sequence", input_path=image_root, camera_id="od")
            annotations = OdViratTinyAnnotationLoader(annotation_path, config).load()

        self.assertEqual(len(annotations), 1)
        self.assertEqual(annotations[0].file_name, "10.jpg")
        self.assertEqual(annotations[0].frame_id, 3)
        self.assertEqual(annotations[0].bbox_xyxy, [1.0, 2.0, 4.0, 6.0])

    def test_construction_loader_reads_yolo_txt_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ["IMG1.jpg", "IMG2.jpg", "IMG10.jpg"]:
                (root / name).write_text("image", encoding="utf-8")
            (root / "IMG2.txt").write_text("7 0.500000 0.500000 0.200000 0.400000\n", encoding="utf-8")

            config = DatasetConfig(
                type="image_sequence",
                input_path=root,
                camera_id="construction",
                start_frame=1,
                frame_limit=1,
            )
            annotations = ConstructionSiteStaticCameraAnnotationLoader(root, config, image_size=[200, 100]).load()

        self.assertEqual(len(annotations), 1)
        self.assertEqual(annotations[0].file_name, "IMG2.jpg")
        self.assertEqual(annotations[0].frame_id, 1)
        self.assertEqual(annotations[0].class_name, "Person")
        self.assertEqual(annotations[0].bbox_xyxy, [80.0, 30.0, 120.0, 70.0])


if __name__ == "__main__":
    unittest.main()
