# Phase 1.2 Workstream A Baseline Lock

## Scope

Phase 1.2 Workstream A의 목적은 main/secondary dataset 기준 baseline run을 고정하고, 이후 adaptive threshold와 neighbor rescue 실험이 줄여야 할 failure type을 분리하는 것이다.

Main dataset:

- config: `configs/datasets/physicalai/physicalai_row0709_after3m.yaml`
- camera: `Camera_0002`
- frame range: `5400 + 600`
- target class: `person`
- diagnostics: `tile_trace`

Secondary dataset:

- config: `configs/datasets/ua_detrac/ua_detrac_mvi_39361.yaml`
- camera: `MVI_39361`
- frame range: `0 + 600`
- target classes: `car`, `bus`, `truck`
- diagnostics: `tile_trace`
- note: source XML marks `camera_state="unstable"`, so this is treated as a robustness cross-check rather than the default-selection dataset.

## Commands

```bash
.venv/bin/python experiments/run_validation_matrix.py \
  --experiment-config configs/experiments/phase1_2_baselines.yaml

.venv/bin/python experiments/run_validation_matrix.py \
  --experiment-config configs/experiments/phase1_2_secondary_ua_detrac_mvi_39361.yaml
```

Taxonomy was generated for each completed run:

```bash
.venv/bin/python tools/reports/classify_boundary_misses.py \
  --run-root outputs/roi_proposal_validation/<run_id>
```

## Output Roots

Main matrix:

- `outputs/validation_matrices/phase1_2_baselines_20260901_142501/`
- comparison frames: `outputs/roi_policy_comparisons/phase1_2_workstream_a_main_20260901_142501/frames/`

Secondary matrix:

- `outputs/validation_matrices/phase1_2_secondary_ua_detrac_mvi_39361_20260901_142611/`
- comparison frames: `outputs/roi_policy_comparisons/phase1_2_workstream_a_secondary_20260901_142611/frames/`

Each run now has:

- `reports/roi_proposal_report.json`
- `reports/roi_proposal_report.md`
- `reports/boundary_misses.jsonl`
- `reports/false_rois.jsonl`
- `reports/boundary_misses.md`

## Main Results

| Run | Contain | Missed GT | Small contain | Missed small | ROI/frame | Tile/frame | Tensor/frame | Reduction | Fallback | False ROI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | 0.544 | 1312 | 0.498 | 1030 | 2.638 | 12.752 | 228360.0 | 0.855 | 20 | 0.556 |
| `practical_default` | 0.641 | 1035 | 0.602 | 816 | 2.638 | 12.752 | 263441.0 | 0.838 | 20 | 0.523 |
| `margin_plus` | 0.655 | 993 | 0.620 | 779 | 2.638 | 12.752 | 282164.2 | 0.829 | 20 | 0.514 |
| `feedback_actual_yolo` | 0.704 | 852 | 0.691 | 634 | 3.522 | 12.752 | 292541.5 | 0.819 | 23 | 0.498 |

## Main Failure Taxonomy

| Run | Margin insufficient | Adjacent tile not selected | Signal missing | Partial target boundary | Low-density noise | Off-target motion |
|---|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | 561 | 342 | 304 | 204 | 666 | 10 |
| `practical_default` | 297 | 329 | 304 | 152 | 666 | 10 |
| `margin_plus` | 255 | 329 | 304 | 137 | 666 | 10 |
| `feedback_actual_yolo` | 210 | 274 | 249 | 375 | 658 | 19 |

## Secondary Results

| Run | Contain | Missed GT | Small contain | Missed small | ROI/frame | Tile/frame | Tensor/frame | Reduction | Fallback | False ROI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | 0.028 | 2570 | 0.092 | 278 | 0.213 | 84.567 | 12144.0 | 0.027 | 569 | 0.750 |
| `practical_default` | 0.000 | 2643 | 0.000 | 306 | 0.000 | 84.567 | 0.0 | 0.000 | 599 | 0.000 |
| `margin_plus` | 0.000 | 2643 | 0.000 | 306 | 0.000 | 84.567 | 0.0 | 0.000 | 599 | 0.000 |
| `feedback_actual_yolo` | 0.000 | 2643 | 0.000 | 306 | 0.000 | 84.567 | 0.0 | 0.000 | 599 | 0.000 |

## Secondary Failure Taxonomy

`MVI_39361` is fallback-dominated. The taxonomy tool skips GT on full-frame/fallback decisions, so non-`tile_baseline` runs show no classified boundary misses even though aggregate containment is zero.

| Run | Margin insufficient | Adjacent tile not selected | Signal missing | Partial target boundary | Low-density noise | Off-target motion |
|---|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | 15 | 2 | 49 | 33 | 20 | 43 |
| `practical_default` | 0 | 0 | 0 | 0 | 0 | 0 |
| `margin_plus` | 0 | 0 | 0 | 0 | 0 | 0 |
| `feedback_actual_yolo` | 0 | 0 | 0 | 0 | 0 | 0 |

## Interpretation

- Main dataset reproduces the Phase 1.1 readiness baseline values, so Phase 1.2 can use this run set as the official baseline lock.
- `practical_default` improves main containment from 0.544 to 0.641 without increasing ROI/frame or selected tile/frame, but tensor cost increases from 228360.0 to 263441.0.
- `margin_plus` recovers additional boundary misses, but it costs more tensor area; it remains a tuning reference rather than the default.
- `feedback_actual_yolo` improves containment most, but increases ROI/frame, tensor cost, fallback count, and partial-boundary false ROI records. It remains a high-recall challenger.
- Main low-density false ROI count remains 666 across tile baseline, practical default, and margin-plus. This is the clearest target for Workstream B.
- Main adjacent-tile misses remain 329 after overlap/margin tuning. This is the clearest target for Workstream C.
- Main signal-missing misses remain 304 without feedback and fall to 249 with actual YOLO feedback. This should be handled later as limited feedback/fallback retuning, not by margin tuning.
- Secondary `MVI_39361` shows that current Phase 1.1 profiles are not robust to the unstable-camera traffic sequence. Treat this as a cross-check failure mode, not as a blocker for main-dataset tuning.
- Secondary root cause is broad motion activation, not absent target signal. In the `tile_baseline` run, average selected tile count is 84.567 out of 144, average motion density is 0.079, and 569 frames fall back because final ROI area is near full frame. By comparison, main `tile_baseline` averages 12.752 selected tiles and 0.0055 motion density.
- Raising the tile density threshold offline on `MVI_39361` reduces selected tiles only at much higher thresholds: threshold 0.10 still averages 38.19 selected tiles, while threshold 0.15 averages 27.61 and threshold 0.20 averages 20.19.
- Target signal still exists in the selected tiles. At threshold 0.01, 92.8% of GT boxes intersect at least one selected tile and 86.0% have their center in a selected tile. The failure is that selected tiles are too broad to remain under ROI area/tile budgets.
- `target_gt_tile_containment=0.000` on `MVI_39361` should not be over-interpreted because many vehicle GT boxes are larger than a single 12x12 tile. Tile intersection or GT-center-in-selected-tile is more informative for this secondary sequence.

## Decision

Workstream A baseline lock is complete for Phase 1.2.

Next implementation order:

1. Workstream B: adaptive tile threshold targeting low-density false ROI.
2. Workstream C: near-threshold neighbor rescue targeting adjacent-tile and residual margin misses.
3. Re-run main matrix with B/C candidates, then use `MVI_39361` as a secondary robustness check.
