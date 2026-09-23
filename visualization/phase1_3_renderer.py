"""Phase 1.3 result visualizations for hybrid ROI gate POCs."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from common import FramePacket, FrameSize, GroundTruthAnnotation, ROI
from common.io import load_yaml_config, read_jsonl, write_json
from common.records import group_by_frame
from data_loader.annotation_loader import create_annotation_loader
from data_loader.dataset_stream import create_dataset_stream, load_dataset_config
from evaluation.metrics.class_filter import filter_gt_by_target_classes
from evaluation.metrics.roi_containment import contains_bbox
from evaluation.reports import road_region_prior as road_prior
from evaluation.reports import static_lightweight_hybrid as light_hybrid
from evaluation.reports import static_tracker_temporal_hybrid as tracker_hybrid
from visualization.primitives import (
    COLOR_GT_CONTAINED,
    COLOR_GT_MISSED,
    COLOR_ROI,
    COLOR_TILE,
    clear_images,
    draw_gt,
    draw_roi,
    draw_title,
    frame_stem,
    load_visualization_dependencies,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS = (
    "outputs/static_tracker_temporal_hybrid_poc/phase1_3_logistics_physicalai_static_tracker_temporal_600_20260917",
    "outputs/static_tracker_temporal_hybrid_poc/phase1_3_general_visdrone_static_tracker_temporal_600_20260917",
    "outputs/static_lightweight_hybrid_poc/phase1_3_retail_mall_static_lightweight_600_20260917",
    "outputs/static_lightweight_hybrid_poc/phase1_3_surveillance_mot17_static_lightweight_600_20260917",
    "outputs/road_region_prior_poc/phase1_3_traffic_road_region_prior_600_20260917",
)


@dataclass(frozen=True)
class Phase13VisualizationSummary:
    output_root: str
    rendered_images: list[str]
    rendered_runs: list[str]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "output_root": self.output_root,
            "rendered_images": self.rendered_images,
            "rendered_runs": self.rendered_runs,
        }


def render_phase1_3_visualizations(
    run_roots: list[str | Path] | None = None,
    output_root: str | Path = "outputs/visualizations/phase1_3",
    max_frames_per_run: int = 6,
) -> Phase13VisualizationSummary:
    cv2, np = load_visualization_dependencies()
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    clear_images(root)

    runs = [load_manifest(path) for path in (run_roots or list(DEFAULT_RUNS))]
    rendered: list[Path] = []
    rendered_runs: list[str] = []

    rendered.append(render_summary_tradeoff_chart(runs, root / "phase1_3_domain_tradeoff.png"))
    rendered.append(render_recommendation_matrix(runs, root / "phase1_3_recommendation_matrix.png"))

    for run in runs:
        run_id = str(run["run_id"])
        pipeline_type = str(run["pipeline_type"])
        rendered_runs.append(run_id)
        if pipeline_type == "static_tracker_temporal_hybrid_poc":
            rendered.extend(render_static_tracker_run(cv2, run, root, max_frames_per_run))
        elif pipeline_type == "static_lightweight_hybrid_poc":
            rendered.extend(render_static_lightweight_run(cv2, np, run, root, max_frames_per_run))
        elif pipeline_type == "road_region_prior_poc":
            rendered.extend(render_road_region_run(cv2, np, run, root, max_frames_per_run))

    summary = Phase13VisualizationSummary(
        output_root=str(root),
        rendered_images=[str(path) for path in rendered],
        rendered_runs=rendered_runs,
    )
    write_json(summary.to_json_dict(), root / "manifest.json")
    return summary


def load_manifest(run_root: str | Path) -> dict[str, Any]:
    root = resolve_project_path(run_root)
    manifest = load_yaml_config(root / "manifest.json")
    manifest["_run_root"] = str(root)
    return manifest


def render_summary_tradeoff_chart(runs: list[dict[str, Any]], output_path: Path) -> Path:
    plt = require_matplotlib()
    rows = []
    for run in runs:
        profile_name, profile = best_profile(run)
        rows.append(
            {
                "domain": domain_label(run),
                "profile": profile_name,
                "recall": profile_recall(profile),
                "reduction": profile_reduction(profile),
            }
        )

    fig, ax = plt.subplots(figsize=(10.8, 5.8))
    y = list(range(len(rows)))
    ax.barh([value - 0.18 for value in y], [row["recall"] for row in rows], height=0.32, label="GT recall")
    ax.barh([value + 0.18 for value in y], [row["reduction"] for row in rows], height=0.32, label="Input reduction")
    ax.set_yticks(y, [row["domain"] for row in rows])
    ax.set_xlim(0, 1.02)
    ax.set_xlabel("ratio")
    ax.set_title("Best observed ROI profile by domain")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="lower right")
    for index, row in enumerate(rows):
        ax.text(min(row["recall"] + 0.015, 0.98), index - 0.18, f"{row['recall']:.3f}", va="center", fontsize=9)
        ax.text(
            min(row["reduction"] + 0.015, 0.98),
            index + 0.18,
            f"{row['reduction']:.3f}",
            va="center",
            fontsize=9,
        )
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def render_recommendation_matrix(runs: list[dict[str, Any]], output_path: Path) -> Path:
    plt = require_matplotlib()
    np = require_numpy()
    labels = [domain_label(run) for run in runs]
    recall = [profile_recall(best_profile(run)[1]) for run in runs]
    reduction = [profile_reduction(best_profile(run)[1]) for run in runs]
    roi_pressure = [roi_pressure_score(best_profile(run)[1]) for run in runs]
    matrix = np.array([recall, reduction, roi_pressure])

    fig, ax = plt.subplots(figsize=(11.5, 3.8))
    im = ax.imshow(matrix, vmin=0, vmax=1, cmap="viridis", aspect="auto")
    ax.set_xticks(range(len(labels)), labels, rotation=25, ha="right")
    ax.set_yticks(range(3), ["GT recall", "Input reduction", "ROI count pressure"])
    ax.set_title("Cross-domain ROI validation signals")
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            ax.text(col, row, f"{matrix[row, col]:.2f}", ha="center", va="center", color="white", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def render_static_tracker_run(
    cv2: Any,
    run: dict[str, Any],
    output_root: Path,
    max_frames: int,
) -> list[Path]:
    run_dir = output_root / str(run["run_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    clear_images(run_dir)

    profile_name, _ = best_profile(run)
    raw_config, dataset_config, annotations, frame_size = load_dataset_context(run)
    grid_shape = tracker_hybrid.GridShape(**run["grid_shape"])
    static_cells = select_tracker_static_cells(annotations, frame_size, grid_shape, profile_name)
    gt_by_frame = group_by_frame(annotations)
    records = records_for_profile(run, profile_name)
    selected = select_tracker_review_records(records, max_frames)
    selected_keys = {(record["camera_id"], int(record["frame_id"])) for record in selected}
    max_index = max((int(record["frame_index"]) for record in selected), default=-1)
    profile = tracker_profile(profile_name)
    memory: list[tuple[int, ROI]] = []
    rendered: list[Path] = []

    for packet in create_dataset_stream(dataset_config):
        frame_index = packet.frame_id - dataset_config.start_frame
        frame_gt = gt_by_frame.get((packet.camera_id, packet.frame_id), [])
        if frame_index % max(1, profile.refresh_interval) == 0:
            memory = [
                (frame_index, tracker_hybrid._roi_from_bbox(gt.bbox_xyxy, packet.original_size, profile.margin_ratio))
                for gt in frame_gt
            ]
        if (packet.camera_id, packet.frame_id) in selected_keys:
            valid_memory = [
                roi for source_index, roi in memory if frame_index - source_index <= profile.guard_stale_frames
            ]
            static_rois = tracker_hybrid._cells_to_rois(static_cells, packet.original_size, grid_shape)
            image = draw_tracker_overlay(cv2, packet, frame_gt, static_cells, grid_shape, static_rois, valid_memory)
            output_path = run_dir / f"{frame_stem(packet.camera_id, packet.frame_id)}_{profile_name}.jpg"
            cv2.imwrite(str(output_path), image)
            rendered.append(output_path)
        if frame_index >= max_index:
            break
    _ = raw_config
    return rendered


def render_static_lightweight_run(
    cv2: Any,
    np: Any,
    run: dict[str, Any],
    output_root: Path,
    max_frames: int,
) -> list[Path]:
    run_dir = output_root / str(run["run_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    clear_images(run_dir)

    profile_name, _ = best_profile(run)
    _, dataset_config, annotations, frame_size = load_dataset_context(run)
    grid_shape = light_hybrid.GridShape(**run["grid_shape"])
    profile = lightweight_profile(profile_name)
    cell_scores = light_hybrid._score_center_cells(annotations, frame_size, grid_shape)
    static_cells = light_hybrid._select_cells(
        cell_scores, grid_shape, profile.static_max_area_ratio, profile.static_dilation_cells
    )
    gt_by_frame = group_by_frame(annotations)
    records = records_for_profile(run, profile_name)
    selected = select_lightweight_review_records(records, max_frames)
    selected_keys = {(record["camera_id"], int(record["frame_id"])) for record in selected}
    rendered: list[Path] = []

    for packet in create_dataset_stream(dataset_config):
        if (packet.camera_id, packet.frame_id) not in selected_keys:
            continue
        selected_cells = select_lightweight_cells(cv2, np, packet, grid_shape, profile, static_cells)
        frame_gt = gt_by_frame.get((packet.camera_id, packet.frame_id), [])
        image = draw_cell_overlay(
            cv2,
            packet,
            frame_gt,
            selected_cells,
            grid_shape,
            title=f"{domain_label(run)} | {profile_name}",
            mode="bbox_cells",
        )
        output_path = run_dir / f"{frame_stem(packet.camera_id, packet.frame_id)}_{profile_name}.jpg"
        cv2.imwrite(str(output_path), image)
        rendered.append(output_path)
        if len(rendered) >= len(selected):
            break
    return rendered


def render_road_region_run(
    cv2: Any,
    np: Any,
    run: dict[str, Any],
    output_root: Path,
    max_frames: int,
) -> list[Path]:
    run_dir = output_root / str(run["run_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    clear_images(run_dir)

    profile_name, _ = best_profile(run)
    _, dataset_config, annotations, frame_size = load_dataset_context(run)
    grid_shape = road_prior.RoadGridShape(**run["grid_shape"])
    selected_cells = road_cells_from_records(run, profile_name)
    gt_by_frame = group_by_frame(annotations)
    selected_keys = select_dense_gt_frame_keys(annotations, max_frames)
    rendered: list[Path] = []

    hit_counts = road_hit_count_grid(run, grid_shape)
    heatmap_path = run_dir / f"{profile_name}_cell_hit_heatmap.png"
    render_cell_heatmap(np, require_matplotlib(), hit_counts, profile_name, heatmap_path)
    rendered.append(heatmap_path)

    for packet in create_dataset_stream(dataset_config):
        if (packet.camera_id, packet.frame_id) not in selected_keys:
            continue
        frame_gt = gt_by_frame.get((packet.camera_id, packet.frame_id), [])
        image = draw_cell_overlay(
            cv2,
            packet,
            frame_gt,
            selected_cells,
            grid_shape,
            title=f"{domain_label(run)} | {profile_name}",
            mode="bbox_cells",
        )
        output_path = run_dir / f"{frame_stem(packet.camera_id, packet.frame_id)}_{profile_name}.jpg"
        cv2.imwrite(str(output_path), image)
        rendered.append(output_path)
        if len(rendered) >= max_frames + 1:
            break
    return rendered


def draw_tracker_overlay(
    cv2: Any,
    packet: FramePacket,
    gt_records: list[GroundTruthAnnotation],
    static_cells: set[tuple[int, int]],
    grid_shape: tracker_hybrid.GridShape,
    static_rois: list[ROI],
    memory_rois: list[ROI],
) -> Any:
    canvas = packet.frame.copy()
    draw_selected_cells(cv2, canvas, packet.original_size, grid_shape, static_cells, COLOR_TILE, alpha=0.18)
    for roi in memory_rois:
        draw_roi(cv2, canvas, roi, COLOR_ROI, "memory")
    for gt in gt_records:
        contained = any(contains_bbox(roi, gt.bbox_xyxy) for roi in memory_rois + static_rois)
        draw_gt(cv2, canvas, gt, contained=contained)
    draw_title(cv2, canvas, "static cells + tracker memory + GT")
    return canvas


def draw_cell_overlay(
    cv2: Any,
    packet: FramePacket,
    gt_records: list[GroundTruthAnnotation],
    selected_cells: set[tuple[int, int]],
    grid_shape: Any,
    title: str,
    mode: str,
) -> Any:
    canvas = packet.frame.copy()
    draw_selected_cells(cv2, canvas, packet.original_size, grid_shape, selected_cells, COLOR_TILE, alpha=0.22)
    for gt in gt_records:
        if mode == "bbox_cells":
            cells = bbox_cells(gt.bbox_xyxy, packet.original_size, grid_shape)
            contained = bool(cells) and cells.issubset(selected_cells)
        else:
            contained = center_cell(gt.bbox_xyxy, packet.original_size, grid_shape) in selected_cells
        draw_gt(cv2, canvas, gt, contained=contained)
    draw_title(cv2, canvas, title)
    return canvas


def draw_selected_cells(
    cv2: Any,
    canvas: Any,
    frame_size: FrameSize,
    grid_shape: Any,
    cells: set[tuple[int, int]],
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    overlay = canvas.copy()
    for row, column in cells:
        x1, y1, x2, y2 = cell_xyxy(row, column, frame_size, grid_shape)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 1)
    cv2.addWeighted(overlay, alpha, canvas, 1 - alpha, 0, canvas)


def select_lightweight_cells(
    cv2: Any,
    np: Any,
    packet: FramePacket,
    grid_shape: light_hybrid.GridShape,
    profile: light_hybrid.StaticLightweightProfile,
    static_cells: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    gray = packet.frame if len(packet.frame.shape) == 2 else cv2.cvtColor(packet.frame, cv2.COLOR_BGR2GRAY)
    edge_map = cv2.Canny(gray, 50, 150)
    laplacian = cv2.Laplacian(gray, cv2.CV_32F)
    edge_signal = normalize_scores(cell_means(np, edge_map, grid_shape))
    texture_signal = normalize_scores(
        [
            (texture + laplace) / 2.0
            for texture, laplace in zip(
                normalize_scores(cell_stddev(np, gray, grid_shape)),
                normalize_scores(cell_abs_means(np, laplacian, grid_shape)),
                strict=True,
            )
        ]
    )
    hybrid_signal = normalize_scores(
        [(edge * 0.55) + (texture * 0.45) for edge, texture in zip(edge_signal, texture_signal, strict=True)]
    )
    scores = {
        "edge": tuple(edge_signal),
        "texture": tuple(texture_signal),
        "hybrid": tuple(hybrid_signal),
    }[profile.signal_name]
    extra_budget_count = max(0, round(grid_shape.cell_count * profile.extra_budget_ratio))
    selected = light_hybrid._select_budgeted_cells(scores, static_cells, grid_shape, extra_budget_count)
    if profile.combined_dilation_cells > 0:
        selected = light_hybrid._dilate_cells(selected, grid_shape, profile.combined_dilation_cells)
    return selected


def load_dataset_context(
    run: dict[str, Any],
) -> tuple[dict[str, Any], Any, list[GroundTruthAnnotation], FrameSize]:
    dataset_path = resolve_project_path(run["dataset_config"])
    raw_config = load_yaml_config(dataset_path)
    dataset_config = load_dataset_config(dataset_path)
    if run.get("limit") is not None:
        from dataclasses import replace

        dataset_config = replace(dataset_config, frame_limit=int(run["limit"]))
    loader = create_annotation_loader(raw_config.get("annotations"), dataset_config)
    annotations = loader.load() if loader else []
    target_classes = tuple(raw_config.get("validation", {}).get("target_classes") or ())
    annotations = list(filter_gt_by_target_classes(annotations, target_classes))
    frame_size = first_frame_size(dataset_config)
    return raw_config, dataset_config, annotations, frame_size


def first_frame_size(dataset_config: Any) -> FrameSize:
    for packet in create_dataset_stream(dataset_config):
        return packet.original_size
    raise ValueError("Dataset stream produced no frames.")


def best_profile(run: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    profiles = run.get("summary", {}).get("profiles", {})
    if not profiles:
        raise ValueError(f"Run has no profile summary: {run.get('run_id')}")
    high_recall = [
        item
        for item in profiles.items()
        if profile_recall(item[1]) >= 0.95
    ]
    if high_recall:
        return max(high_recall, key=lambda item: (profile_reduction(item[1]), profile_recall(item[1])))
    return max(profiles.items(), key=lambda item: (profile_recall(item[1]), profile_reduction(item[1])))


def profile_recall(profile: dict[str, Any]) -> float:
    for key in ("target_gt_recall", "bbox_gt_recall", "center_gt_recall"):
        if key in profile:
            return float(profile[key])
    return 0.0


def profile_reduction(profile: dict[str, Any]) -> float:
    for key in ("effective_input_area_reduction", "input_area_reduction"):
        if key in profile:
            return float(profile[key])
    return 0.0


def roi_pressure_score(profile: dict[str, Any]) -> float:
    roi_count = profile.get("average_combined_roi_count_per_memory_frame")
    if roi_count is None:
        return 0.0
    return min(1.0, float(roi_count) / 300.0)


def domain_label(run: dict[str, Any]) -> str:
    name = str(run.get("experiment_name", run.get("run_id", "")))
    if "traffic" in name:
        return "Traffic"
    if "logistics" in name or "physicalai" in name:
        return "Logistics"
    if "surveillance" in name or "mot17" in name:
        return "Surveillance"
    if "retail" in name or "mall" in name:
        return "Retail"
    if "general" in name or "visdrone" in name:
        return "General"
    return name


def records_for_profile(run: dict[str, Any], profile_name: str) -> list[dict[str, Any]]:
    outputs = run.get("outputs", {})
    path = outputs.get("frame_records") or outputs.get("cell_records")
    if not path:
        return []
    return [record for record in read_jsonl(resolve_project_path(path)) if record.get("profile_name") == profile_name]


def select_tracker_review_records(records: list[dict[str, Any]], max_frames: int) -> list[dict[str, Any]]:
    memory = [record for record in records if not record.get("is_refresh_frame")]
    misses = [
        record
        for record in memory
        if int(record.get("target_gt_count", 0)) > int(record.get("contained_gt_count", 0))
    ]
    hits = [
        record
        for record in memory
        if int(record.get("target_gt_count", 0)) and int(record.get("target_gt_count", 0)) == int(record.get("contained_gt_count", 0))
    ]
    return (misses[: max_frames // 2] + hits[: max_frames - len(misses[: max_frames // 2])])[:max_frames]


def select_lightweight_review_records(records: list[dict[str, Any]], max_frames: int) -> list[dict[str, Any]]:
    misses = [
        record
        for record in records
        if int(record.get("target_gt_count", 0)) > int(record.get("bbox_contained_gt_count", 0))
    ]
    dense = sorted(records, key=lambda record: int(record.get("target_gt_count", 0)), reverse=True)
    selected = []
    seen = set()
    for record in misses + dense:
        key = (record["camera_id"], record["frame_id"])
        if key in seen:
            continue
        selected.append(record)
        seen.add(key)
        if len(selected) >= max_frames:
            break
    return selected


def select_dense_gt_frame_keys(annotations: list[GroundTruthAnnotation], max_frames: int) -> set[tuple[str, int]]:
    counts: Counter[tuple[str, int]] = Counter((gt.camera_id, gt.frame_id) for gt in annotations)
    return {key for key, _ in counts.most_common(max_frames)}


def select_tracker_static_cells(
    annotations: list[GroundTruthAnnotation],
    frame_size: FrameSize,
    grid_shape: tracker_hybrid.GridShape,
    profile_name: str,
) -> set[tuple[int, int]]:
    profile = tracker_profile(profile_name)
    cell_scores = tracker_hybrid._score_center_cells(annotations, frame_size, grid_shape)
    return tracker_hybrid._select_cells(cell_scores, grid_shape, profile.static_max_area_ratio, profile.static_dilation_cells)


def tracker_profile(profile_name: str) -> tracker_hybrid.StaticTrackerHybridProfile:
    return next(profile for profile in tracker_hybrid.default_static_tracker_hybrid_profiles() if profile.name == profile_name)


def lightweight_profile(profile_name: str) -> light_hybrid.StaticLightweightProfile:
    return next(profile for profile in light_hybrid.default_static_lightweight_profiles() if profile.name == profile_name)


def road_cells_from_records(run: dict[str, Any], profile_name: str) -> set[tuple[int, int]]:
    path = resolve_project_path(run["outputs"]["cell_records"])
    cells = set()
    for record in read_jsonl(path):
        if profile_name in record.get("selected_profiles", []):
            cells.add((int(record["row"]), int(record["column"])))
    return cells


def road_hit_count_grid(run: dict[str, Any], grid_shape: road_prior.RoadGridShape) -> list[list[int]]:
    path = resolve_project_path(run["outputs"]["cell_records"])
    grid = [[0 for _ in range(grid_shape.columns)] for _ in range(grid_shape.rows)]
    for record in read_jsonl(path):
        grid[int(record["row"])][int(record["column"])] = int(record.get("hit_count", 0))
    return grid


def render_cell_heatmap(np: Any, plt: Any, hit_counts: list[list[int]], title: str, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    image = ax.imshow(np.array(hit_counts), cmap="magma", aspect="auto")
    ax.set_title(f"Traffic occupied cell heatmap | {title}")
    ax.set_xlabel("column")
    ax.set_ylabel("row")
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def cell_xyxy(row: int, column: int, frame_size: FrameSize, grid_shape: Any) -> tuple[int, int, int, int]:
    x1 = round(column * frame_size.width / grid_shape.columns)
    x2 = round((column + 1) * frame_size.width / grid_shape.columns)
    y1 = round(row * frame_size.height / grid_shape.rows)
    y2 = round((row + 1) * frame_size.height / grid_shape.rows)
    return x1, y1, x2, y2


def bbox_cells(bbox_xyxy: list[float], frame_size: FrameSize, grid_shape: Any) -> set[tuple[int, int]]:
    x1, y1, x2, y2 = bbox_xyxy
    left = axis_cell(x1, frame_size.width, grid_shape.columns)
    right = axis_cell(max(x1, x2 - 1), frame_size.width, grid_shape.columns)
    top = axis_cell(y1, frame_size.height, grid_shape.rows)
    bottom = axis_cell(max(y1, y2 - 1), frame_size.height, grid_shape.rows)
    return {(row, column) for row in range(top, bottom + 1) for column in range(left, right + 1)}


def center_cell(bbox_xyxy: list[float], frame_size: FrameSize, grid_shape: Any) -> tuple[int, int]:
    x1, y1, x2, y2 = bbox_xyxy
    return axis_cell((y1 + y2) / 2, frame_size.height, grid_shape.rows), axis_cell(
        (x1 + x2) / 2, frame_size.width, grid_shape.columns
    )


def axis_cell(value: float, axis_size: int, cell_count: int) -> int:
    if axis_size <= 0 or cell_count <= 0:
        return 0
    normalized = min(max(value / axis_size, 0.0), 0.999999)
    return min(cell_count - 1, int(normalized * cell_count))


def cell_means(np: Any, image: Any, grid_shape: Any) -> list[float]:
    return [cell_stat(np, image, grid_shape, row, column, "mean") for row in range(grid_shape.rows) for column in range(grid_shape.columns)]


def cell_abs_means(np: Any, image: Any, grid_shape: Any) -> list[float]:
    return [cell_stat(np, image, grid_shape, row, column, "abs_mean") for row in range(grid_shape.rows) for column in range(grid_shape.columns)]


def cell_stddev(np: Any, image: Any, grid_shape: Any) -> list[float]:
    return [cell_stat(np, image, grid_shape, row, column, "std") for row in range(grid_shape.rows) for column in range(grid_shape.columns)]


def cell_stat(np: Any, image: Any, grid_shape: Any, row: int, column: int, mode: str) -> float:
    height, width = image.shape[:2]
    y1 = round(row * height / grid_shape.rows)
    y2 = round((row + 1) * height / grid_shape.rows)
    x1 = round(column * width / grid_shape.columns)
    x2 = round((column + 1) * width / grid_shape.columns)
    cell = image[y1:y2, x1:x2]
    if cell.size == 0:
        return 0.0
    if mode == "mean":
        return float(np.mean(cell))
    if mode == "abs_mean":
        return float(np.mean(np.abs(cell)))
    if mode == "std":
        return float(np.std(cell))
    raise ValueError(f"Unsupported cell stat mode: {mode}")


def normalize_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    min_score = min(scores)
    max_score = max(scores)
    if max_score <= min_score:
        return [0.0 for _ in scores]
    return [(score - min_score) / (max_score - min_score) for score in scores]


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def require_matplotlib():
    try:
        os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / "outputs" / "matplotlib"))
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("matplotlib is required for Phase 1.3 visualizations.") from exc
    return plt


def require_numpy():
    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("NumPy is required for Phase 1.3 visualizations.") from exc
    return np
