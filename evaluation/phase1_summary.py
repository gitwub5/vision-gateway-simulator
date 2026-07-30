"""Summarize Phase 1 experiment outputs across profiles and ROI-count buckets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from statistics import mean
from typing import Any

from evaluation.comparison_report import read_detection_jsonl
from evaluation.detection_metrics import match_detections_by_iou
from gpu_inference.yolo_roi import read_gate_frame_metadata_jsonl, read_roi_metadata_jsonl


@dataclass(frozen=True)
class ProfileSummary:
    run_id: str
    experiment_name: str
    output_root: str
    dataset_config: str
    gate_config: str
    include_full_frame_checks: bool
    pseudo_recall: float
    roi_containment_rate: float
    input_pixel_area_reduction: float
    yolo_call_count: int
    full_frame_check_count: int
    average_roi_count: float
    average_roi_area_ratio: float
    roi_yolo_average_latency_ms: float
    gate_average_latency_ms: float
    failure_case_count: int

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RoiCountBucketSummary:
    bucket: str
    frame_count: int
    average_roi_count: float
    average_total_roi_area_ratio: float
    roi_yolo_call_count: int
    full_frame_check_count: int
    estimated_average_roi_yolo_latency_ms: float
    full_frame_baseline_latency_ms: float
    estimated_latency_delta_vs_full_frame_ms: float
    pseudo_recall: float
    failure_case_count: int
    notes: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize_profile_run(run_root: str | Path) -> ProfileSummary:
    root = Path(run_root)
    manifest = _read_json(root / "manifest.json")
    report = _read_json(root / "reports" / "comparison_report.json")
    roi_metrics = _read_json(root / "reports" / "roi_yolo_metrics.json")
    frame_records = read_gate_frame_metadata_jsonl(root / "roi_metadata" / "gate_decisions.jsonl")

    detection = report["detection"]
    roi = report["roi"]
    workload = report["workload"]
    latency = report["latency"]
    inputs = manifest.get("inputs", {})

    return ProfileSummary(
        run_id=str(manifest.get("run_id", root.name)),
        experiment_name=str(manifest.get("experiment_name", root.name)),
        output_root=str(root),
        dataset_config=str(inputs.get("dataset_config", "")),
        gate_config=str(inputs.get("gate_config", "")),
        include_full_frame_checks=bool(inputs.get("include_full_frame_checks", True)),
        pseudo_recall=float(detection.get("pseudo_recall", 0.0)),
        roi_containment_rate=float(roi.get("containment_rate", 0.0)),
        input_pixel_area_reduction=float(workload.get("input_pixel_area_reduction", 0.0)),
        yolo_call_count=int(roi_metrics.get("yolo_call_count", 0)),
        full_frame_check_count=int(roi_metrics.get("full_frame_check_call_count", 0)),
        average_roi_count=float(roi.get("average_roi_count", 0.0)),
        average_roi_area_ratio=float(roi.get("average_roi_area_ratio", 0.0)),
        roi_yolo_average_latency_ms=float(roi_metrics.get("average_latency_ms", 0.0)),
        gate_average_latency_ms=float(latency.get("gate_average_latency_ms", 0.0)),
        failure_case_count=_count_failure_images(root),
    )


def summarize_profile_runs(run_roots: list[str | Path]) -> list[ProfileSummary]:
    return [summarize_profile_run(path) for path in run_roots]


def profile_summaries_to_markdown(summaries: list[ProfileSummary]) -> str:
    lines = [
        "# Phase 1 Profile Summary",
        "",
        "| Run | Pseudo recall | ROI containment | Input area reduction | YOLO calls | Full-frame checks | Avg ROI count | Avg ROI area | ROI latency ms | Gate latency ms | Failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    summary.experiment_name,
                    _format_ratio(summary.pseudo_recall),
                    _format_ratio(summary.roi_containment_rate),
                    _format_ratio(summary.input_pixel_area_reduction),
                    str(summary.yolo_call_count),
                    str(summary.full_frame_check_count),
                    f"{summary.average_roi_count:.3f}",
                    _format_ratio(summary.average_roi_area_ratio),
                    f"{summary.roi_yolo_average_latency_ms:.3f}",
                    f"{summary.gate_average_latency_ms:.3f}",
                    str(summary.failure_case_count),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def summarize_roi_count_latency(run_root: str | Path, iou_threshold: float = 0.5) -> list[RoiCountBucketSummary]:
    root = Path(run_root)
    roi_records = read_roi_metadata_jsonl(root / "roi_metadata" / "rule_roi.jsonl")
    frame_records = read_gate_frame_metadata_jsonl(root / "roi_metadata" / "gate_decisions.jsonl")
    full_frame_detections = read_detection_jsonl(root / "detections" / "full_frame.jsonl")
    roi_detections = read_detection_jsonl(root / "detections" / "roi_yolo.jsonl")
    full_frame_metrics = _read_json(root / "reports" / "full_frame_metrics.json")
    roi_metrics = _read_json(root / "reports" / "roi_yolo_metrics.json")

    roi_by_frame: dict[tuple[str, int], list] = {}
    for record in roi_records:
        roi_by_frame.setdefault((record.camera_id, record.frame_id), []).append(record)

    full_detections_by_frame = _group_detections(full_frame_detections)
    roi_detections_by_frame = _group_detections(roi_detections)

    frame_size_area_by_key = {
        (record.camera_id, record.frame_id): record.original_frame_size.area()
        for record in frame_records
    }
    fallback_frames = {
        (record.camera_id, record.frame_id)
        for record in frame_records
        if record.should_run_full_frame
    }

    buckets: dict[str, list[tuple[str, int]]] = {}
    for record in frame_records:
        key = (record.camera_id, record.frame_id)
        buckets.setdefault(_bucket_name(record.roi_count), []).append(key)

    estimated_latency_per_call = float(roi_metrics.get("average_latency_ms", 0.0))
    full_frame_latency = float(full_frame_metrics.get("average_latency_ms", 0.0))
    notes = [
        "ROI metrics currently store aggregate latency only; bucket latency is estimated from average latency per YOLO call.",
    ]

    summaries: list[RoiCountBucketSummary] = []
    for bucket in ["0", "1", "2-3", "4-5", "6-8", "9+"]:
        keys = buckets.get(bucket, [])
        roi_counts = [len(roi_by_frame.get(key, [])) for key in keys]
        total_area_ratios = [
            _total_roi_area_ratio(roi_by_frame.get(key, []), frame_size_area_by_key.get(key, 0))
            for key in keys
        ]
        roi_call_count = sum(roi_counts)
        full_check_count = sum(1 for key in keys if key in fallback_frames)
        call_count = roi_call_count + full_check_count
        reference = [
            detection for key in keys for detection in full_detections_by_frame.get(key, [])
        ]
        candidate = [
            detection for key in keys for detection in roi_detections_by_frame.get(key, [])
        ]
        detection_summary = match_detections_by_iou(reference, candidate, iou_threshold)
        estimated_latency = estimated_latency_per_call * call_count / len(keys) if keys else 0.0

        summaries.append(
            RoiCountBucketSummary(
                bucket=bucket,
                frame_count=len(keys),
                average_roi_count=mean(roi_counts) if roi_counts else 0.0,
                average_total_roi_area_ratio=mean(total_area_ratios) if total_area_ratios else 0.0,
                roi_yolo_call_count=roi_call_count,
                full_frame_check_count=full_check_count,
                estimated_average_roi_yolo_latency_ms=estimated_latency,
                full_frame_baseline_latency_ms=full_frame_latency,
                estimated_latency_delta_vs_full_frame_ms=estimated_latency - full_frame_latency,
                pseudo_recall=detection_summary.pseudo_recall,
                failure_case_count=(
                    detection_summary.reference_detection_count
                    - detection_summary.matched_detection_count
                ),
                notes=notes,
            )
        )
    return summaries


def roi_bucket_summaries_to_markdown(summaries: list[RoiCountBucketSummary]) -> str:
    lines = [
        "# ROI Count Latency Benchmark",
        "",
        "| Bucket | Frames | Avg ROI count | Avg ROI area | ROI calls | Full checks | Est ROI latency ms | Full latency ms | Delta ms | Pseudo recall | Failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    summary.bucket,
                    str(summary.frame_count),
                    f"{summary.average_roi_count:.3f}",
                    _format_ratio(summary.average_total_roi_area_ratio),
                    str(summary.roi_yolo_call_count),
                    str(summary.full_frame_check_count),
                    f"{summary.estimated_average_roi_yolo_latency_ms:.3f}",
                    f"{summary.full_frame_baseline_latency_ms:.3f}",
                    f"{summary.estimated_latency_delta_vs_full_frame_ms:.3f}",
                    _format_ratio(summary.pseudo_recall),
                    str(summary.failure_case_count),
                ]
            )
            + " |"
        )
    if summaries and summaries[0].notes:
        lines.extend(["", "## Notes", ""])
        for note in summaries[0].notes:
            lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def write_summary_json(data: list[ProfileSummary] | list[RoiCountBucketSummary], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump([item.to_json_dict() for item in data], file, ensure_ascii=False, indent=2)
        file.write("\n")


def write_text(text: str, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _count_failure_images(root: Path) -> int:
    failures = root / "visualizations" / "failures"
    if not failures.exists():
        return 0
    return sum(1 for path in failures.iterdir() if path.is_file())


def _bucket_name(roi_count: int) -> str:
    if roi_count <= 0:
        return "0"
    if roi_count == 1:
        return "1"
    if roi_count <= 3:
        return "2-3"
    if roi_count <= 5:
        return "4-5"
    if roi_count <= 8:
        return "6-8"
    return "9+"


def _total_roi_area_ratio(roi_records: list, frame_area: int) -> float:
    if frame_area <= 0:
        return 0.0
    return sum(record.roi.area() for record in roi_records) / frame_area


def _group_detections(detections: list) -> dict[tuple[str, int], list]:
    grouped: dict[tuple[str, int], list] = {}
    for detection in detections:
        grouped.setdefault((detection.camera_id, detection.frame_id), []).append(detection)
    return grouped


def _format_ratio(value: float) -> str:
    return f"{value:.3f}"
