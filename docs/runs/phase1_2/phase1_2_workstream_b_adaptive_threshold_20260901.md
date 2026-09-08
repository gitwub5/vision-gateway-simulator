# Phase 1.2 Workstream B Adaptive Tile Threshold

## Scope

Workstream B tests whether adaptive tile thresholding can reduce false ROI and tensor cost without materially hurting target containment.

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

## Candidates

| Candidate | Config | Status |
|---|---|---|
| `adaptive_threshold_ema` | `configs/roi_generator/phase1_2/adaptive/profile_adaptive_tile_threshold_ema.yaml` | Disable |
| `rare_tile_guard` | `configs/roi_generator/phase1_2/adaptive/profile_rare_tile_guard.yaml` | Tune |

`adaptive_threshold_ema` raises each tile threshold from its recent EMA. It reduced selected tiles and tensor cost, but it also suppressed target-supporting low-density tiles and caused a large recall regression.

`rare_tile_guard` keeps the global threshold but suppresses weak tiles that have enough history and a low activation rate. It reduced false ROI and cost with a smaller recall loss.

## Commands

```bash
.venv/bin/python experiments/run_validation_matrix.py \
  --experiment-config configs/experiments/phase1_2_adaptive_threshold.yaml

.venv/bin/python experiments/run_validation_matrix.py \
  --experiment-config configs/experiments/phase1_2_secondary_adaptive_threshold_ua_detrac_mvi_39361.yaml
```

Taxonomy was generated for each completed run:

```bash
.venv/bin/python tools/reports/classify_boundary_misses.py \
  --run-root outputs/roi_proposal_validation/<run_id>
```

## Output Roots

Main matrix:

- `outputs/validation_matrices/phase1_2_adaptive_threshold_20260901_145552/`
- comparison frames: `outputs/roi_policy_comparisons/phase1_2_workstream_b_adaptive_threshold_main_20260901_145552/frames/`

Secondary matrix:

- `outputs/validation_matrices/phase1_2_secondary_adaptive_threshold_ua_detrac_mvi_39361_20260901_145700/`

## Main Results

| Run | Contain | Missed GT | Small contain | Missed small | ROI/frame | Tile/frame | Tensor/frame | Reduction | Fallback | False ROI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | 0.544 | 1312 | 0.498 | 1030 | 2.638 | 12.752 | 228360.0 | 0.855 | 20 | 0.556 |
| `practical_default` | 0.641 | 1035 | 0.602 | 816 | 2.638 | 12.752 | 263441.0 | 0.838 | 20 | 0.523 |
| `adaptive_threshold_ema` | 0.179 | 2364 | 0.123 | 1798 | 2.573 | 8.420 | 142334.0 | 0.898 | 19 | 0.788 |
| `rare_tile_guard` | 0.625 | 1081 | 0.588 | 845 | 2.398 | 11.462 | 245620.7 | 0.848 | 19 | 0.485 |

## Main Failure Taxonomy

| Run | Margin insufficient | Adjacent tile not selected | Signal missing | Partial target boundary | Low-density noise | Off-target motion |
|---|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | 561 | 342 | 304 | 204 | 666 | 10 |
| `practical_default` | 297 | 329 | 304 | 152 | 666 | 10 |
| `adaptive_threshold_ema` | 785 | 544 | 936 | 619 | 587 | 10 |
| `rare_tile_guard` | 322 | 336 | 324 | 171 | 517 | 10 |

## Secondary Results

| Run | Contain | Missed GT | Small contain | Missed small | ROI/frame | Tile/frame | Tensor/frame | Reduction | Fallback | False ROI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | 0.028 | 2570 | 0.092 | 278 | 0.213 | 84.567 | 12144.0 | 0.027 | 569 | 0.750 |
| `practical_default` | 0.000 | 2643 | 0.000 | 306 | 0.000 | 84.567 | 0.0 | 0.000 | 599 | 0.000 |
| `rare_tile_guard` | 0.000 | 2643 | 0.000 | 306 | 0.000 | 84.508 | 0.0 | 0.000 | 599 | 0.000 |

## Interpretation

- Static threshold sweep on the main tile trace showed that raising the threshold reduces selected tiles but also drops GT tile intersection: threshold 0.01 gives 0.825 GT intersection, while 0.02 drops to 0.738.
- `adaptive_threshold_ema` confirms that broad per-tile threshold raising is too aggressive for the main dataset. It cuts tile/frame from 12.752 to 8.420, but containment falls from 0.641 to 0.179 versus `practical_default`.
- `rare_tile_guard` is the first useful Workstream B signal. It reduces false ROI rate from 0.523 to 0.485, low-density noise records from 666 to 517, ROI/frame from 2.638 to 2.398, and tensor/frame from 263441.0 to 245620.7.
- `rare_tile_guard` still loses containment, from 0.641 to 0.625. It should not replace `practical_default` as-is.
- Secondary `MVI_39361` remains fallback-dominated. `rare_tile_guard` suppresses only 35 tile selections out of more than 50k selected tile records, so it does not address unstable-camera global motion activation.

## Decision

- `adaptive_threshold_ema`: Disable.
- `rare_tile_guard`: Keep/Tune as a cost-reduction candidate.
- Workstream B is complete as a standalone workstream.
- `adaptive_threshold_ema` is kept in code/config for experiment reproducibility, but its registry status is disabled and it is excluded from the default Workstream B matrix.
- `rare_tile_guard` remains active as a Workstream C combination candidate, not as a standalone default.
- `scene_profile_threshold` is deferred. `MVI_39361` indicates global motion/scene-state handling rather than simple adaptive thresholding.

Next step:

1. Combine `rare_tile_guard` with Workstream C neighbor rescue and test whether recall loss can be recovered.
2. Defer `MVI_39361` improvement to global-motion/scene-state handling unless Phase 1.2 scope expands.
