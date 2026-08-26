"""Render side-by-side ROI policy comparison images from saved validation runs."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_loader import create_dataset_stream, load_dataset_config
from evaluation.metrics.roi_containment import contains_bbox


@dataclass(frozen=True)
class PolicyRun:
    label: str
    root: Path
    rois_by_frame: dict[int, list[dict[str, Any]]]
    frames_by_frame: dict[int, dict[str, Any]]
    tiles_by_frame: dict[int, list[dict[str, Any]]]
    feedback_by_frame: dict[int, list[dict[str, Any]]]


def main() -> None:
    args = parse_args()
    summary = render_roi_policy_comparison(
        dataset_config_path=args.dataset_config,
        output_dir=args.output_dir,
        run_specs=args.run,
        max_frames=args.max_frames,
        frame_limit=args.frame_limit,
        frame_step=args.frame_step,
        panel_width=args.panel_width,
    )
    print(json.dumps(summary, indent=2))


def render_roi_policy_comparison(
    dataset_config_path: str | Path,
    output_dir: str | Path,
    run_specs: list[str],
    max_frames: int = 80,
    frame_limit: int | None = None,
    frame_step: int = 1,
    panel_width: int = 960,
) -> dict[str, Any]:
    cv2, np = load_visualization_dependencies()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    clear_jpgs(output_path)

    policy_runs = [load_policy_run(spec) for spec in run_specs]
    gt_by_frame = load_ground_truth(policy_runs[0].root / "annotations" / "ground_truth.jsonl")
    selected_frames = select_frames(
        policy_runs=policy_runs,
        gt_by_frame=gt_by_frame,
        max_frames=max_frames,
        frame_step=frame_step,
    )
    frames_to_render = set(selected_frames)

    dataset_config = load_dataset_config(dataset_config_path)
    if frame_limit is not None:
        dataset_config = replace(dataset_config, frame_limit=frame_limit)
    rendered = 0
    for packet in create_dataset_stream(dataset_config):
        if packet.frame_id not in frames_to_render:
            continue
        image = draw_comparison(
            cv2=cv2,
            np=np,
            frame=packet.frame,
            camera_id=packet.camera_id,
            frame_id=packet.frame_id,
            policy_runs=policy_runs,
            gt_records=gt_by_frame.get(packet.frame_id, []),
            panel_width=panel_width,
        )
        cv2.imwrite(str(output_path / f"{packet.camera_id}_f{packet.frame_id:06d}_roi_policy_compare.jpg"), image)
        rendered += 1
        if rendered >= len(frames_to_render):
            break

    summary = {
        "output_dir": str(output_path),
        "rendered_images": rendered,
        "selected_frames": selected_frames,
        "runs": [{"label": run.label, "root": str(run.root)} for run in policy_runs],
    }
    (output_path / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render side-by-side ROI policy comparison images.")
    parser.add_argument("--dataset-config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        help="Policy spec in label=outputs/roi_proposal_validation/<run_id> form.",
    )
    parser.add_argument("--max-frames", type=int, default=80)
    parser.add_argument("--frame-limit", type=int, default=None)
    parser.add_argument("--frame-step", type=int, default=1)
    parser.add_argument("--panel-width", type=int, default=960)
    return parser.parse_args()


def load_policy_run(spec: str) -> PolicyRun:
    if "=" not in spec:
        raise ValueError(f"Run spec must be label=path: {spec}")
    label, raw_path = spec.split("=", 1)
    root = Path(raw_path)
    rois = group_jsonl_by_frame(root / "roi_metadata" / "rule_roi.jsonl")
    frames = index_jsonl_by_frame(root / "roi_metadata" / "gate_decisions.jsonl")
    tile_path = root / "roi_metadata" / "tile_metadata.jsonl"
    tiles = group_jsonl_by_frame(tile_path) if tile_path.exists() else {}
    feedback_path = root / "detections" / "reference_feedback_full_frame.jsonl"
    feedback = group_jsonl_by_frame(feedback_path) if feedback_path.exists() else {}
    return PolicyRun(
        label=label,
        root=root,
        rois_by_frame=rois,
        frames_by_frame=frames,
        tiles_by_frame=tiles,
        feedback_by_frame=feedback,
    )


def load_ground_truth(path: Path) -> dict[int, list[dict[str, Any]]]:
    return group_jsonl_by_frame(path)


def group_jsonl_by_frame(path: Path) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in read_jsonl(path):
        grouped[int(record["frame_id"])].append(record)
    return dict(grouped)


def index_jsonl_by_frame(path: Path) -> dict[int, dict[str, Any]]:
    return {int(record["frame_id"]): record for record in read_jsonl(path)}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def select_frames(
    policy_runs: list[PolicyRun],
    gt_by_frame: dict[int, list[dict[str, Any]]],
    max_frames: int,
    frame_step: int,
) -> list[int]:
    scored: list[tuple[float, int]] = []
    for frame_id, gt_records in gt_by_frame.items():
        if frame_step > 1 and frame_id % frame_step != 0:
            continue
        if not gt_records:
            continue
        contains = [
            count_contained_gt(run.rois_by_frame.get(frame_id, []), gt_records)
            for run in policy_runs
        ]
        roi_counts = [len(run.rois_by_frame.get(frame_id, [])) for run in policy_runs]
        fallback_count = sum(
            1 for run in policy_runs if run.frames_by_frame.get(frame_id, {}).get("should_run_full_frame")
        )
        feedback_count = sum(
            int(run.frames_by_frame.get(frame_id, {}).get("feedback_assisted_roi_count", 0))
            for run in policy_runs
        )
        missed_min = len(gt_records) - max(contains)
        spread = max(contains) - min(contains)
        roi_spread = max(roi_counts) - min(roi_counts)
        score = spread * 1000 + missed_min * 50 + feedback_count * 20 + roi_spread + fallback_count
        if score > 0:
            scored.append((score, frame_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = sorted(frame_id for _, frame_id in scored[:max_frames])
    if selected:
        return selected
    return sorted(gt_by_frame)[:max_frames]


def count_contained_gt(rois: list[dict[str, Any]], gt_records: list[dict[str, Any]]) -> int:
    return sum(1 for gt in gt_records if any(roi_contains_bbox(roi, gt["bbox_xyxy"]) for roi in rois))


def roi_contains_bbox(roi_record: dict[str, Any], bbox_xyxy: list[float]) -> bool:
    x, y, w, h = roi_record["roi_xywh"]
    roi = SimpleRoi(int(x), int(y), int(w), int(h))
    return contains_bbox(roi, bbox_xyxy)


class SimpleRoi:
    def __init__(self, x: int, y: int, w: int, h: int) -> None:
        self.x = x
        self.y = y
        self.w = w
        self.h = h


def draw_comparison(
    cv2: Any,
    np: Any,
    frame: Any,
    camera_id: str,
    frame_id: int,
    policy_runs: list[PolicyRun],
    gt_records: list[dict[str, Any]],
    panel_width: int,
) -> Any:
    panels = [
        draw_policy_panel(cv2, frame, frame_id, run, gt_records, panel_width)
        for run in policy_runs
    ]
    image = np.concatenate(panels, axis=1)
    legend = draw_legend(cv2, np, image.shape[1], 76, camera_id, frame_id)
    return np.concatenate([image, legend], axis=0)


def draw_policy_panel(
    cv2: Any,
    frame: Any,
    frame_id: int,
    run: PolicyRun,
    gt_records: list[dict[str, Any]],
    panel_width: int,
) -> Any:
    height, width = frame.shape[:2]
    scale = panel_width / width
    panel_height = int(round(height * scale))
    panel = cv2.resize(frame, (panel_width, panel_height), interpolation=cv2.INTER_AREA)
    rois = run.rois_by_frame.get(frame_id, [])
    frame_record = run.frames_by_frame.get(frame_id, {})
    tiles = run.tiles_by_frame.get(frame_id, [])
    feedback = run.feedback_by_frame.get(frame_id, [])
    final_rois = classify_final_rois(rois, int(frame_record.get("feedback_assisted_roi_count", 0)))
    tile_rois = [roi for roi, origin in final_rois if origin == "tile"]
    feedback_rois = [roi for roi, origin in final_rois if origin == "feedback"]

    if should_draw_tile_grid(frame_record, tiles, tile_rois):
        draw_tile_grid(cv2, panel, width, height, scale)
        draw_active_tiles(cv2, panel, tiles, tile_rois, width, height, scale)
    for detection in feedback:
        draw_bbox(cv2, panel, detection["bbox_xyxy"], scale, (80, 220, 80), "ref box")
    for roi in tile_rois:
        x, y, w, h = roi["roi_xywh"]
        draw_filled_rect_xyxy(cv2, panel, [x, y, x + w, y + h], scale, (0, 220, 255), 0.16)
        draw_rect_xyxy(cv2, panel, [x, y, x + w, y + h], scale, (0, 220, 255), "tile ROI")
    for roi in feedback_rois:
        x, y, w, h = roi["roi_xywh"]
        draw_filled_rect_xyxy(cv2, panel, [x, y, x + w, y + h], scale, (80, 220, 80), 0.18)
        draw_rect_xyxy(cv2, panel, [x, y, x + w, y + h], scale, (80, 220, 80), "fb ROI")
    for gt in gt_records:
        contained = any(roi_contains_bbox(roi, gt["bbox_xyxy"]) for roi in rois)
        color = (255, 0, 255) if contained else (0, 0, 255)
        label = "GT hit" if contained else "GT miss"
        draw_bbox(cv2, panel, gt["bbox_xyxy"], scale, color, label)

    cv2.rectangle(panel, (0, 0), (panel_width, 66), (18, 18, 18), -1)
    title = run.label
    metrics = (
        f"roi={len(rois)} gt_hit={count_contained_gt(rois, gt_records)}/{len(gt_records)} "
        f"tiles={int(frame_record.get('selected_tile_count', 0))} "
        f"fb={int(frame_record.get('feedback_assisted_roi_count', 0))} "
        f"full={bool(frame_record.get('should_run_full_frame', False))}"
    )
    cv2.putText(panel, title, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (245, 245, 245), 2, cv2.LINE_AA)
    cv2.putText(panel, metrics, (12, 51), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (235, 235, 235), 1, cv2.LINE_AA)
    return panel


def classify_final_rois(
    rois: list[dict[str, Any]],
    feedback_assisted_roi_count: int,
) -> list[tuple[dict[str, Any], str]]:
    if feedback_assisted_roi_count <= 0:
        return [(roi, "tile") for roi in rois]
    feedback_ids = {
        id(roi)
        for roi in sorted(rois, key=lambda roi: float(roi.get("score", 0.0)), reverse=True)[
            :feedback_assisted_roi_count
        ]
    }
    return [(roi, "feedback" if id(roi) in feedback_ids else "tile") for roi in rois]


def should_draw_tile_grid(
    frame_record: dict[str, Any],
    tiles: list[dict[str, Any]],
    tile_rois: list[dict[str, Any]],
) -> bool:
    return bool(tiles) or int(frame_record.get("selected_tile_count", 0)) > 0 or bool(tile_rois)


def draw_tile_grid(cv2: Any, panel: Any, frame_width: int, frame_height: int, scale: float) -> None:
    tile_width = frame_width / 12
    tile_height = frame_height / 12
    color = (92, 92, 92)
    for col in range(1, 12):
        x = int(round(col * tile_width * scale))
        cv2.line(panel, (x, 0), (x, int(round(frame_height * scale))), color, 1, cv2.LINE_AA)
    for row in range(1, 12):
        y = int(round(row * tile_height * scale))
        cv2.line(panel, (0, y), (int(round(frame_width * scale)), y), color, 1, cv2.LINE_AA)


def draw_active_tiles(
    cv2: Any,
    panel: Any,
    tiles: list[dict[str, Any]],
    tile_rois: list[dict[str, Any]],
    frame_width: int,
    frame_height: int,
    scale: float,
) -> None:
    if tiles:
        active_tiles = [tile["bbox_xywh"] for tile in tiles if tile.get("selected")]
    else:
        active_tiles = infer_active_tiles_from_rois(tile_rois, frame_width, frame_height)
    for x, y, w, h in active_tiles:
        draw_filled_rect_xyxy(cv2, panel, [x, y, x + w, y + h], scale, (180, 120, 40), 0.14)
        draw_rect_xyxy(cv2, panel, [x, y, x + w, y + h], scale, (180, 120, 40), "")


def infer_active_tiles_from_rois(
    tile_rois: list[dict[str, Any]],
    frame_width: int,
    frame_height: int,
) -> list[list[int]]:
    inferred: list[list[int]] = []
    tile_width = frame_width / 12
    tile_height = frame_height / 12
    for row in range(12):
        for col in range(12):
            x = int(round(col * tile_width))
            y = int(round(row * tile_height))
            w = int(round((col + 1) * tile_width)) - x
            h = int(round((row + 1) * tile_height)) - y
            tile_bbox = [x, y, x + w, y + h]
            if any(overlap_ratio(tile_bbox, roi_xyxy(roi)) > 0.05 for roi in tile_rois):
                inferred.append([x, y, w, h])
    return inferred


def roi_xyxy(roi_record: dict[str, Any]) -> list[int]:
    x, y, w, h = roi_record["roi_xywh"]
    return [int(x), int(y), int(x + w), int(y + h)]


def overlap_ratio(left: list[int], right: list[int]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[2], right[2])
    y2 = min(left[3], right[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    left_area = max(0, left[2] - left[0]) * max(0, left[3] - left[1])
    return intersection / left_area if left_area else 0.0


def draw_bbox(cv2: Any, panel: Any, bbox_xyxy: list[float], scale: float, color: tuple[int, int, int], label: str) -> None:
    draw_rect_xyxy(cv2, panel, bbox_xyxy, scale, color, label)


def draw_rect_xyxy(
    cv2: Any,
    panel: Any,
    bbox_xyxy: list[float],
    scale: float,
    color: tuple[int, int, int],
    label: str,
) -> None:
    x1, y1, x2, y2 = [int(round(value * scale)) for value in bbox_xyxy]
    cv2.rectangle(panel, (x1, y1), (x2, y2), color, 2)
    if not label:
        return
    y_text = max(16, y1 - 5)
    cv2.putText(panel, label, (x1, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.44, color, 1, cv2.LINE_AA)


def draw_filled_rect_xyxy(
    cv2: Any,
    panel: Any,
    bbox_xyxy: list[float],
    scale: float,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    x1, y1, x2, y2 = [int(round(value * scale)) for value in bbox_xyxy]
    overlay = panel.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    cv2.addWeighted(overlay, alpha, panel, 1 - alpha, 0, panel)


def draw_legend(cv2: Any, np: Any, width: int, height: int, camera_id: str, frame_id: int) -> Any:
    legend = np.zeros((height, width, 3), dtype=np.uint8)
    legend[:, :] = (22, 22, 22)
    entries = [
        ("yellow: active tile ROI/inference area", (0, 220, 255)),
        ("blue: selected tile/grid cell", (180, 120, 40)),
        ("green: feedback ROI/ref box", (80, 220, 80)),
        ("magenta: GT contained", (255, 0, 255)),
        ("red: GT missed", (0, 0, 255)),
    ]
    cv2.putText(
        legend,
        f"{camera_id} frame={frame_id}",
        (12, 26),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (245, 245, 245),
        1,
        cv2.LINE_AA,
    )
    x = 12
    y = 58
    for label, color in entries:
        cv2.rectangle(legend, (x, y - 16), (x + 24, y + 4), color, 2)
        cv2.putText(legend, label, (x + 34, y), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (235, 235, 235), 1, cv2.LINE_AA)
        x += 370
    return legend


def clear_jpgs(directory: Path) -> None:
    for path in directory.glob("*.jpg"):
        if path.is_file():
            path.unlink()


def load_visualization_dependencies():
    try:
        import cv2
        import numpy as np
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "OpenCV and NumPy are required for ROI policy comparison rendering. "
            "Install project dependencies with `pip install -r requirements.txt`."
        ) from exc
    return cv2, np


if __name__ == "__main__":
    main()
