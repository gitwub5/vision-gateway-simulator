"""Ground-truth validation report for annotated datasets."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from common import Detection, GroundTruthAnnotation, ROIMetadata
from common.io import write_json, write_text
from common.records import format_ratio
from evaluation.class_filter import (
    filter_detections_by_target_classes,
    filter_gt_by_target_classes,
    normalize_class_name,
    normalize_target_classes,
)
from evaluation.detection_metrics import bbox_iou
from evaluation.roi_containment import contains_bbox
from gpu_inference.yolo_roi import read_roi_metadata_jsonl


@dataclass(frozen=True)
class AnnotationQuality:
    completeness: str = "unknown"
    expected_exhaustive: bool = False
    notes: tuple[str, ...] = ()
    unreliable_metrics: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "AnnotationQuality":
        if not data:
            return cls()
        notes = tuple(str(note) for note in data.get("notes", []) if note is not None)
        unreliable_metrics = tuple(
            str(metric) for metric in data.get("unreliable_metrics", []) if metric is not None
        )
        return cls(
            completeness=str(data.get("completeness", "unknown")),
            expected_exhaustive=bool(data.get("expected_exhaustive", False)),
            notes=notes,
            unreliable_metrics=unreliable_metrics,
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "completeness": self.completeness,
            "expected_exhaustive": self.expected_exhaustive,
            "notes": list(self.notes),
            "unreliable_metrics": list(self.unreliable_metrics),
        }


@dataclass(frozen=True)
class GtReportInputs:
    ground_truth: Path
    full_frame_detections: Path
    roi_detections: Path
    roi_metadata: Path
    report_json: Path
    report_markdown: Path

    def to_json_dict(self) -> dict[str, str]:
        return {
            "ground_truth": str(self.ground_truth),
            "full_frame_detections": str(self.full_frame_detections),
            "roi_detections": str(self.roi_detections),
            "roi_metadata": str(self.roi_metadata),
            "report_json": str(self.report_json),
            "report_markdown": str(self.report_markdown),
        }


@dataclass(frozen=True)
class DetectorGtSummary:
    detector_name: str
    gt_object_count: int
    detection_count: int
    matched_gt_count: int
    missed_gt_count: int
    duplicate_detection_count: int
    iou_threshold: float
    class_recall: dict[str, float]

    @property
    def object_recall(self) -> float:
        if self.gt_object_count == 0:
            return 0.0
        return self.matched_gt_count / self.gt_object_count

    @property
    def duplicate_detection_rate(self) -> float:
        if self.detection_count == 0:
            return 0.0
        return self.duplicate_detection_count / self.detection_count

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["object_recall"] = self.object_recall
        data["duplicate_detection_rate"] = self.duplicate_detection_rate
        return data


@dataclass(frozen=True)
class GtRoiSummary:
    gt_object_count: int
    contained_gt_count: int
    roi_record_count: int
    false_roi_count: int

    @property
    def gt_roi_containment(self) -> float:
        if self.gt_object_count == 0:
            return 0.0
        return self.contained_gt_count / self.gt_object_count

    @property
    def false_roi_rate(self) -> float:
        if self.roi_record_count == 0:
            return 0.0
        return self.false_roi_count / self.roi_record_count

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["gt_roi_containment"] = self.gt_roi_containment
        data["false_roi_rate"] = self.false_roi_rate
        return data


@dataclass(frozen=True)
class GtReport:
    inputs: GtReportInputs
    full_frame: DetectorGtSummary
    roi_yolo: DetectorGtSummary
    roi: GtRoiSummary
    annotation_quality: AnnotationQuality = AnnotationQuality()
    target_classes: tuple[str, ...] = ()

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "inputs": self.inputs.to_json_dict(),
            "annotation_quality": self.annotation_quality.to_json_dict(),
            "target_classes": list(self.target_classes),
            "full_frame": self.full_frame.to_json_dict(),
            "roi_yolo": self.roi_yolo.to_json_dict(),
            "roi": self.roi.to_json_dict(),
        }

    def to_markdown(self) -> str:
        lines = [
            "# GT Validation Report",
            "",
            "## Summary",
            "",
            f"- Full-frame GT object recall: {format_ratio(self.full_frame.object_recall)}",
            f"- ROI-gated GT object recall: {format_ratio(self.roi_yolo.object_recall)}",
            f"- GT ROI containment: {format_ratio(self.roi.gt_roi_containment)}",
            f"- Missed GT objects, ROI-gated: {self.roi_yolo.missed_gt_count}",
            f"- False ROI rate: {format_ratio(self.roi.false_roi_rate)}",
            f"- ROI-gated duplicate detection rate: {format_ratio(self.roi_yolo.duplicate_detection_rate)}",
            "",
            "## Target Scope",
            "",
            f"- Target classes: `{', '.join(self.target_classes) if self.target_classes else 'all'}`",
            "",
            "## Annotation Quality",
            "",
            f"- Completeness: `{self.annotation_quality.completeness}`",
            f"- Expected exhaustive: `{str(self.annotation_quality.expected_exhaustive).lower()}`",
        ]
        if self.annotation_quality.notes:
            lines.append("- Notes:")
            for note in self.annotation_quality.notes:
                lines.append(f"  - {note}")
        if self.annotation_quality.unreliable_metrics:
            lines.append("- Metrics requiring caution:")
            for metric in self.annotation_quality.unreliable_metrics:
                lines.append(f"  - `{metric}`")
        lines.extend(
            [
                "",
                "## Class Recall",
                "",
                "| Class | Full-frame | ROI-gated |",
                "|---|---:|---:|",
            ]
        )
        for class_name in sorted(set(self.full_frame.class_recall) | set(self.roi_yolo.class_recall)):
            lines.append(
                f"| {class_name} | {format_ratio(self.full_frame.class_recall.get(class_name, 0.0))} "
                f"| {format_ratio(self.roi_yolo.class_recall.get(class_name, 0.0))} |"
            )
        lines.extend(["", "## Inputs", ""])
        for key, value in self.inputs.to_json_dict().items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
        return "\n".join(lines)


def build_gt_report(
    inputs: GtReportInputs,
    ground_truth: Iterable[GroundTruthAnnotation],
    full_frame_detections: Iterable[Detection],
    roi_detections: Iterable[Detection],
    iou_threshold: float = 0.5,
    annotation_quality: AnnotationQuality | None = None,
    target_classes: Iterable[str] | None = None,
) -> GtReport:
    normalized_target_classes = normalize_target_classes(target_classes)
    gt_records = filter_gt_by_target_classes(ground_truth, normalized_target_classes)
    full_detection_records = filter_detections_by_target_classes(full_frame_detections, normalized_target_classes)
    roi_detection_records = filter_detections_by_target_classes(roi_detections, normalized_target_classes)
    roi_records = read_roi_metadata_jsonl(inputs.roi_metadata)
    return GtReport(
        inputs=inputs,
        full_frame=summarize_detector_gt(
            "full_frame_yolo",
            gt_records,
            full_detection_records,
            iou_threshold,
        ),
        roi_yolo=summarize_detector_gt(
            "roi_yolo",
            gt_records,
            roi_detection_records,
            iou_threshold,
        ),
        roi=summarize_gt_roi_containment(gt_records, roi_records),
        annotation_quality=annotation_quality or AnnotationQuality(),
        target_classes=tuple(target_classes or ()),
    )


def summarize_detector_gt(
    detector_name: str,
    ground_truth: Iterable[GroundTruthAnnotation],
    detections: Iterable[Detection],
    iou_threshold: float = 0.5,
) -> DetectorGtSummary:
    gt_records = list(ground_truth)
    detection_records = list(detections)
    gt_by_key = _group_gt_by_key(gt_records)
    matched_gt_indexes: set[int] = set()
    duplicate_detection_count = 0

    for detection in detection_records:
        candidates = gt_by_key.get(
            (detection.camera_id, detection.frame_id, normalize_class_name(detection.class_name)),
            [],
        )
        best_index = None
        best_iou = 0.0
        for gt_index, gt in candidates:
            iou = bbox_iou(gt.bbox_xyxy, detection.bbox_xyxy)
            if iou > best_iou:
                best_iou = iou
                best_index = gt_index
        if best_index is None or best_iou < iou_threshold:
            continue
        if best_index in matched_gt_indexes:
            duplicate_detection_count += 1
        else:
            matched_gt_indexes.add(best_index)

    class_recall = _class_recall(gt_records, matched_gt_indexes)
    return DetectorGtSummary(
        detector_name=detector_name,
        gt_object_count=len(gt_records),
        detection_count=len(detection_records),
        matched_gt_count=len(matched_gt_indexes),
        missed_gt_count=len(gt_records) - len(matched_gt_indexes),
        duplicate_detection_count=duplicate_detection_count,
        iou_threshold=iou_threshold,
        class_recall=class_recall,
    )


def summarize_gt_roi_containment(
    ground_truth: Iterable[GroundTruthAnnotation],
    roi_records: Iterable[ROIMetadata],
) -> GtRoiSummary:
    gt_records = list(ground_truth)
    rois = list(roi_records)
    rois_by_frame: dict[tuple[str, int], list[ROIMetadata]] = defaultdict(list)
    for roi_record in rois:
        rois_by_frame[(roi_record.camera_id, roi_record.frame_id)].append(roi_record)

    contained_gt_count = 0
    for gt in gt_records:
        frame_rois = rois_by_frame.get((gt.camera_id, gt.frame_id), [])
        if any(contains_bbox(roi_record.roi, gt.bbox_xyxy) for roi_record in frame_rois):
            contained_gt_count += 1

    false_roi_count = 0
    gt_by_frame: dict[tuple[str, int], list[GroundTruthAnnotation]] = defaultdict(list)
    for gt in gt_records:
        gt_by_frame[(gt.camera_id, gt.frame_id)].append(gt)
    for roi_record in rois:
        frame_gt = gt_by_frame.get((roi_record.camera_id, roi_record.frame_id), [])
        if not any(contains_bbox(roi_record.roi, gt.bbox_xyxy) for gt in frame_gt):
            false_roi_count += 1

    return GtRoiSummary(
        gt_object_count=len(gt_records),
        contained_gt_count=contained_gt_count,
        roi_record_count=len(rois),
        false_roi_count=false_roi_count,
    )


def write_gt_report_json(report: GtReport, output_path: str | Path) -> None:
    write_json(report.to_json_dict(), output_path)


def write_gt_report_markdown(report: GtReport, output_path: str | Path) -> None:
    write_text(report.to_markdown(), output_path)


def _group_gt_by_key(
    gt_records: list[GroundTruthAnnotation],
) -> dict[tuple[str, int, str], list[tuple[int, GroundTruthAnnotation]]]:
    grouped: dict[tuple[str, int, str], list[tuple[int, GroundTruthAnnotation]]] = defaultdict(list)
    for index, gt in enumerate(gt_records):
        grouped[(gt.camera_id, gt.frame_id, normalize_class_name(gt.class_name))].append((index, gt))
    return grouped


def _class_recall(gt_records: list[GroundTruthAnnotation], matched_gt_indexes: set[int]) -> dict[str, float]:
    totals: dict[str, int] = defaultdict(int)
    matched: dict[str, int] = defaultdict(int)
    for index, gt in enumerate(gt_records):
        totals[gt.class_name] += 1
        if index in matched_gt_indexes:
            matched[gt.class_name] += 1
    return {
        class_name: matched[class_name] / total if total else 0.0
        for class_name, total in totals.items()
    }

