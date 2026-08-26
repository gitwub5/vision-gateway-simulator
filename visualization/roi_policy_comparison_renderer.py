"""Render side-by-side ROI policy comparison images from saved validation runs."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_loader import create_dataset_stream, load_dataset_config
from evaluation.metrics.roi_containment import contains_bbox
from visualization.artifacts import (
    FrameKey,
    RoiRunArtifacts,
    ensure_compatible_runs,
    load_run_spec,
)
from visualization.frame_selection import count_contained_gt, select_frame_keys
from visualization.primitives import (
    COLOR_FEEDBACK,
    COLOR_GT_CONTAINED,
    COLOR_GT_MISSED,
    COLOR_ROI,
    COLOR_TILE,
    clear_images,
    draw_filled_xyxy,
    draw_gt_record,
    draw_xyxy,
    load_visualization_dependencies,
)


PolicyRun = RoiRunArtifacts


def main() -> None:
    args = parse_args()
    summary = render_roi_policy_comparison(
        dataset_config_path=args.dataset_config,
        output_dir=args.output_dir,
        run_specs=args.run,
        selection_preset=args.preset,
        explicit_frame_ids=args.frame,
        max_frames=args.max_frames,
        frame_limit=args.frame_limit,
        frame_step=args.frame_step,
        panel_width=args.panel_width,
    )
    print(json.dumps(summary, indent=2))


def render_roi_policy_comparison(
    dataset_config_path: str | Path | None,
    output_dir: str | Path,
    run_specs: list[str],
    selection_preset: str = "disagreement",
    explicit_frame_ids: list[int] | None = None,
    max_frames: int = 80,
    frame_limit: int | None = None,
    frame_step: int = 1,
    panel_width: int = 960,
) -> dict[str, Any]:
    cv2, np = load_visualization_dependencies()
    output_path = Path(output_dir)
    frames_output = output_path / "frames"
    frames_output.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)
    clear_images(frames_output)

    policy_runs = [load_policy_run(spec) for spec in run_specs]
    compatibility = ensure_compatible_runs(policy_runs)
    explicit_keys = [
        (str(compatibility["camera_id"]), frame_id)
        for frame_id in (explicit_frame_ids or [])
    ]
    selected_frames = select_frame_keys(
        runs=policy_runs,
        preset="explicit" if explicit_keys else selection_preset,
        max_frames=max_frames,
        explicit=explicit_keys,
    )
    if frame_step > 1:
        selected_frames = [key for key in selected_frames if key[1] % frame_step == 0]
    frames_to_render = set(selected_frames)

    dataset_config = load_dataset_config(dataset_config_path or policy_runs[0].dataset_config_path)
    dataset_config = replace(
        dataset_config,
        start_frame=int(compatibility["start_frame"]),
        frame_limit=int(compatibility["effective_frame_limit"]),
    )
    if frame_limit is not None:
        dataset_config = replace(dataset_config, frame_limit=frame_limit)
    rendered = 0
    for packet in create_dataset_stream(dataset_config):
        key = (packet.camera_id, packet.frame_id)
        if key not in frames_to_render:
            continue
        image = draw_comparison(
            cv2=cv2,
            np=np,
            frame=packet.frame,
            camera_id=packet.camera_id,
            frame_id=packet.frame_id,
            policy_runs=policy_runs,
            gt_records=policy_runs[0].ground_truth_by_frame.get(key, []),
            panel_width=panel_width,
        )
        cv2.imwrite(str(frames_output / f"{packet.camera_id}_f{packet.frame_id:06d}_roi_policy_compare.jpg"), image)
        rendered += 1
        if rendered >= len(frames_to_render):
            break

    summary = {
        "output_dir": str(output_path),
        "selection_preset": "explicit" if explicit_keys else selection_preset,
        "rendered_images": rendered,
        "selected_frames": [[camera_id, frame_id] for camera_id, frame_id in selected_frames],
        "compatibility": compatibility,
        "runs": [{"label": run.label, "root": str(run.root)} for run in policy_runs],
    }
    (output_path / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render side-by-side ROI policy comparison images.")
    parser.add_argument("--dataset-config", default=None, help="Deprecated: resolved from each run manifest.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        help="Policy spec in label=outputs/roi_proposal_validation/<run_id> form.",
    )
    parser.add_argument("--max-frames", type=int, default=80)
    parser.add_argument("--preset", choices=["disagreement", "missed", "cost"], default="disagreement")
    parser.add_argument("--frame", action="append", type=int, default=[])
    parser.add_argument("--frame-limit", type=int, default=None)
    parser.add_argument("--frame-step", type=int, default=1)
    parser.add_argument("--panel-width", type=int, default=960)
    return parser.parse_args()


def load_policy_run(spec: str) -> PolicyRun:
    return load_run_spec(spec)


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
    key = (camera_id, frame_id)
    panels = [
        draw_policy_panel(cv2, frame, key, run, gt_records, panel_width)
        for run in policy_runs
    ]
    image = np.concatenate(panels, axis=1)
    legend = draw_legend(cv2, np, image.shape[1], 76, camera_id, frame_id)
    return np.concatenate([image, legend], axis=0)


def draw_policy_panel(
    cv2: Any,
    frame: Any,
    key: FrameKey,
    run: PolicyRun,
    gt_records: list[dict[str, Any]],
    panel_width: int,
) -> Any:
    height, width = frame.shape[:2]
    scale = panel_width / width
    panel_height = int(round(height * scale))
    panel = cv2.resize(frame, (panel_width, panel_height), interpolation=cv2.INTER_AREA)
    rois = run.rois_by_frame.get(key, [])
    frame_record = run.frames_by_frame.get(key, {})
    tiles = run.tiles_by_frame.get(key, [])
    feedback = run.feedback_by_frame.get(key, [])

    if run.tile_trace_available and should_draw_tile_grid(frame_record, tiles, rois):
        draw_tile_grid(cv2, panel, width, height, scale)
        draw_active_tiles(cv2, panel, tiles, scale)
    for detection in feedback:
        draw_bbox(cv2, panel, detection["bbox_xyxy"], scale, COLOR_FEEDBACK, "ref box")
    for roi in rois:
        x, y, w, h = roi["roi_xywh"]
        draw_filled_rect_xyxy(cv2, panel, [x, y, x + w, y + h], scale, COLOR_ROI, 0.16)
        draw_rect_xyxy(cv2, panel, [x, y, x + w, y + h], scale, COLOR_ROI, "final ROI")
    for gt in gt_records:
        contained = any(roi_contains_bbox(roi, gt["bbox_xyxy"]) for roi in rois)
        draw_gt_record(cv2, panel, gt, contained, scale)

    cv2.rectangle(panel, (0, 0), (panel_width, 66), (18, 18, 18), -1)
    title = run.label
    metrics = (
        f"roi={len(rois)} gt_hit={count_contained_gt(rois, gt_records)}/{len(gt_records)} "
        f"tiles={int(frame_record.get('selected_tile_count', 0))} "
        f"fb={int(frame_record.get('feedback_assisted_roi_count', 0))} "
        f"full={bool(frame_record.get('should_run_full_frame', False))} "
        f"tile_trace={'yes' if run.tile_trace_available else 'unavailable'}"
    )
    cv2.putText(panel, title, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (245, 245, 245), 2, cv2.LINE_AA)
    cv2.putText(panel, metrics, (12, 51), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (235, 235, 235), 1, cv2.LINE_AA)
    return panel


def should_draw_tile_grid(
    frame_record: dict[str, Any],
    tiles: list[dict[str, Any]],
    final_rois: list[dict[str, Any]],
) -> bool:
    is_tile_policy = frame_record.get("policy_label") in {"tile_mask", "hybrid_component_tile"}
    return is_tile_policy and (
        bool(tiles)
        or int(frame_record.get("selected_tile_count", 0)) > 0
        or bool(final_rois)
    )


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
    scale: float,
) -> None:
    active_tiles = [tile["bbox_xywh"] for tile in tiles if tile.get("selected")]
    for x, y, w, h in active_tiles:
        draw_filled_rect_xyxy(cv2, panel, [x, y, x + w, y + h], scale, COLOR_TILE, 0.14)
        draw_rect_xyxy(cv2, panel, [x, y, x + w, y + h], scale, COLOR_TILE, "")


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
    draw_xyxy(cv2, panel, bbox_xyxy, color, label, scale)


def draw_filled_rect_xyxy(
    cv2: Any,
    panel: Any,
    bbox_xyxy: list[float],
    scale: float,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    draw_filled_xyxy(cv2, panel, bbox_xyxy, color, alpha, scale)


def draw_legend(cv2: Any, np: Any, width: int, height: int, camera_id: str, frame_id: int) -> Any:
    legend = np.zeros((height, width, 3), dtype=np.uint8)
    legend[:, :] = (22, 22, 22)
    entries = [
        ("ROI area", COLOR_ROI),
        ("selected tile", COLOR_TILE),
        ("feedback", COLOR_FEEDBACK),
        ("GT contained", COLOR_GT_CONTAINED),
        ("GT missed", COLOR_GT_MISSED),
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
    y = 58
    spacing = max(180, width // len(entries))
    for index, (label, color) in enumerate(entries):
        x = 12 + index * spacing
        cv2.rectangle(legend, (x, y - 16), (x + 24, y + 4), color, 2)
        cv2.putText(legend, label, (x + 34, y), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (235, 235, 235), 1, cv2.LINE_AA)
    return legend


if __name__ == "__main__":
    main()
