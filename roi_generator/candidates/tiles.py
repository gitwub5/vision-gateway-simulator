"""Fixed-grid tile candidate metadata helpers."""

from __future__ import annotations

from common import FrameSize, ROI
from roi_generator.trace import TileTrace


def tile_traces_from_motion_map(
    motion_map,
    frame_size: FrameSize,
    grid_rows: int,
    grid_cols: int,
    motion_density_threshold: float,
) -> list[TileTrace]:
    rows = max(1, int(grid_rows))
    cols = max(1, int(grid_cols))
    traces: list[TileTrace] = []
    tile_id = 1

    for row in range(rows):
        y1 = round(row * frame_size.height / rows)
        y2 = round((row + 1) * frame_size.height / rows)
        for col in range(cols):
            x1 = round(col * frame_size.width / cols)
            x2 = round((col + 1) * frame_size.width / cols)
            width = max(0, x2 - x1)
            height = max(0, y2 - y1)
            density = _motion_density(motion_map, x1, y1, x2, y2)
            traces.append(
                TileTrace(
                    tile_id=tile_id,
                    row=row,
                    col=col,
                    bbox=ROI(x=x1, y=y1, w=width, h=height, score=density, coord_system="analysis_frame"),
                    motion_density=density,
                    selected=density > motion_density_threshold,
                )
            )
            tile_id += 1
    return traces


def selected_tile_count(tile_traces: list[TileTrace]) -> int:
    return sum(1 for tile in tile_traces if tile.selected)


def scale_tile_traces_to_original(
    tile_traces: list[TileTrace],
    analysis_size: FrameSize,
    original_size: FrameSize,
) -> list[TileTrace]:
    scale_x = original_size.width / analysis_size.width
    scale_y = original_size.height / analysis_size.height
    return [
        TileTrace(
            tile_id=tile.tile_id,
            row=tile.row,
            col=tile.col,
            bbox=ROI(
                x=round(tile.bbox.x * scale_x),
                y=round(tile.bbox.y * scale_y),
                w=round(tile.bbox.w * scale_x),
                h=round(tile.bbox.h * scale_y),
                score=tile.bbox.score,
                coord_system="original_frame",
            ),
            motion_density=tile.motion_density,
            selected=tile.selected,
        )
        for tile in tile_traces
    ]


def _motion_density(motion_map, x1: int, y1: int, x2: int, y2: int) -> float:
    tile = motion_map[y1:y2, x1:x2]
    area = max(1, int(tile.size))
    try:
        active = int((tile > 0).sum())
    except TypeError:
        return 0.0
    return active / area
