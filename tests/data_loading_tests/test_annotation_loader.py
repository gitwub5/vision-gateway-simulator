from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from data_loader import DatasetConfig
from data_loader.annotation_loader import (
    OdViratTinyAnnotationLoader,
    PhysicalAiSmartSpacesAnnotationLoader,
    UaDetracAnnotationLoader,
    create_annotation_loader,
)


class AnnotationLoaderTest(unittest.TestCase):
    def test_create_annotation_loader_ignores_none_type(self) -> None:
        config = DatasetConfig(type="video", input_path=Path("sample.mp4"), camera_id="sample")

        loader = create_annotation_loader({"type": "none", "input_path": None}, config)

        self.assertIsNone(loader)

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

    def test_ua_detrac_loader_maps_xml_frames_to_dataset_frame_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_root = root / "MVI_39031"
            image_root.mkdir()
            for name in ["img00001.jpg", "img00002.jpg", "img00010.jpg"]:
                (image_root / name).write_text("image", encoding="utf-8")
            annotation_path = root / "MVI_39031.xml"
            annotation_path.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<sequence name="MVI_39031">
  <frame num="1">
    <target_list>
      <target id="7">
        <box left="10" top="20" width="30" height="40"/>
        <attribute vehicle_type="car"/>
      </target>
    </target_list>
  </frame>
  <frame num="2">
    <target_list>
      <target id="8">
        <box left="1.5" top="2.5" width="3.0" height="4.0"/>
        <attribute vehicle_type="van"/>
      </target>
    </target_list>
  </frame>
</sequence>
""",
                encoding="utf-8",
            )

            config = DatasetConfig(
                type="image_sequence",
                input_path=image_root,
                camera_id="MVI_39031",
                start_frame=1,
                frame_limit=1,
            )
            annotations = UaDetracAnnotationLoader(annotation_path, config).load()

        self.assertEqual(len(annotations), 1)
        self.assertEqual(annotations[0].file_name, "img00002.jpg")
        self.assertEqual(annotations[0].frame_id, 1)
        self.assertEqual(annotations[0].class_name, "car")
        self.assertEqual(annotations[0].bbox_xyxy, [1.5, 2.5, 4.5, 6.5])

    def test_physicalai_loader_filters_camera_and_frame_range(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            annotation_path = root / "ground_truth.json"
            annotation_path.write_text(
                json.dumps(
                    {
                        "frames": [
                            {
                                "frame_id": 4,
                                "objects": [
                                    {
                                        "object_id": "ignored_before_start",
                                        "class": "Human",
                                        "cameras": {
                                            "Camera_0002": {"bbox": [1, 2, 11, 22]},
                                        },
                                    }
                                ],
                            },
                            {
                                "frame_id": 5,
                                "objects": [
                                    {
                                        "object_id": "person_1",
                                        "class": "Human",
                                        "cameras": {
                                            "Camera_0002": {"bbox": [10, 20, 30, 40]},
                                            "Camera_0003": {"bbox": [1, 2, 3, 4]},
                                        },
                                    },
                                    {
                                        "object_id": "forklift_1",
                                        "type": "Forklift",
                                        "camera_id": "Camera_0002",
                                        "bbox": {"left": 5, "top": 6, "width": 7, "height": 8},
                                    },
                                ],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            config = DatasetConfig(
                type="video",
                input_path=root / "Camera_0002.mp4",
                camera_id="Camera_0002",
                start_frame=5,
                frame_limit=1,
            )
            annotations = PhysicalAiSmartSpacesAnnotationLoader(annotation_path, config).load()

        self.assertEqual(len(annotations), 2)
        self.assertEqual(annotations[0].frame_id, 5)
        self.assertEqual(annotations[0].class_name, "person")
        self.assertEqual(annotations[0].bbox_xyxy, [10.0, 20.0, 30.0, 40.0])
        self.assertEqual(annotations[1].class_name, "forklift")
        self.assertEqual(annotations[1].bbox_xyxy, [5.0, 6.0, 12.0, 14.0])

    def test_physicalai_loader_reads_official_frame_keyed_visible_boxes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            annotation_path = root / "ground_truth.json"
            annotation_path.write_text(
                json.dumps(
                    {
                        "7": [
                            {
                                "object_type": "PalletTruck",
                                "object_id": 42,
                                "3d_location": [1, 2, 3],
                                "2d_bounding_box_visible": {
                                    "camera_0002": [10, 20, 30, 40],
                                    "camera_0003": [1, 2, 3, 4],
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            config = DatasetConfig(
                type="video",
                input_path=root / "Camera_0002.mp4",
                camera_id="Camera_0002",
                start_frame=7,
                frame_limit=1,
            )
            annotations = PhysicalAiSmartSpacesAnnotationLoader(annotation_path, config).load()

        self.assertEqual(len(annotations), 1)
        self.assertEqual(annotations[0].frame_id, 7)
        self.assertEqual(annotations[0].class_name, "pallet_truck")
        self.assertEqual(annotations[0].bbox_xyxy, [10.0, 20.0, 30.0, 40.0])


if __name__ == "__main__":
    unittest.main()
