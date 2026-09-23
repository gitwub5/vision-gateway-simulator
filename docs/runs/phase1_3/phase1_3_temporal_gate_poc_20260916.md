# Phase 1.3-B Temporal Gate POC - 2026-09-16

## Scope

Phase 1.3-B에서는 ROI를 공간 crop으로만 보지 않고, GPU detector를 실행할 frame 자체를 줄이는 temporal gate를 검증했다.

이 run의 목적은 기존 motion/tile ROI를 고도화하는 것이 아니라, CCTV 입력에서 가장 단순하게 적용 가능한 시간축 selection이 domain별로 유효한지 확인하는 것이다.

공통 조건:

- Frame limit: 120
- Analysis frame width: 160 px
- Output root: `outputs/temporal_gate_poc/`
- Matrix root: `outputs/temporal_gate_matrices/phase1_3_temporal_gate_20260916_152806`
- Profiles:
  - `process_all`
  - `fixed_skip_2`
  - `fixed_skip_5`
  - `fixed_skip_10`
  - `stability_0_01_refresh_30`
  - `stability_0_02_refresh_30`
  - `stability_0_05_refresh_30`

## Implementation

Added:

- `evaluation/reports/temporal_gate.py`
- `experiments/phase1_3/run_temporal_gate_poc.py`
- `experiments/phase1_3/run_temporal_gate_matrix.py`
- `tests/evaluation_tests/test_temporal_gate_report.py`

The runner reuses existing dataset loaders and annotation loaders. For each frame, it records:

- target frame 여부
- target GT count
- downsampled grayscale frame delta mean
- downsampled grayscale frame delta p95

Then it evaluates fixed-interval skipping and simple scene-delta gate profiles against target-frame recall and target-GT recall.

## Matrix Runs

| Coverage Group | Run root |
|---|---|
| Traffic / parking | `outputs/temporal_gate_poc/phase1_3_traffic_ua_detrac_mvi_39361_temporal_gate_20260916_152806` |
| Logistics / smart factory | `outputs/temporal_gate_poc/phase1_3_logistics_physicalai_row0709_after3m_temporal_gate_20260916_152806` |
| Surveillance / security | `outputs/temporal_gate_poc/phase1_3_surveillance_mot17_04_temporal_gate_20260916_152806` |
| Retail / space analytics | `outputs/temporal_gate_poc/phase1_3_retail_mall_dataset_temporal_gate_20260916_152806` |
| General camera-motion stress | `outputs/temporal_gate_poc/phase1_3_general_visdrone_uav0000086_temporal_gate_20260916_152806` |

## Summary

All 5 selected 120-frame samples contain target objects in every frame. Under a frame-level recall metric, fixed frame skipping therefore creates an almost direct tradeoff between detector-call reduction and recall loss.

| Dataset | Best non-all temporal profile by target-GT recall | Reduction | Target-GT recall | Interpretation |
|---|---|---:|---:|---|
| Traffic / UA-DETRAC | `stability_0_01_refresh_30` | 0.467 | 0.523 | Some camera/object motion triggers the gate, but recall is too low for standalone use. |
| Logistics / PhysicalAI | `fixed_skip_2` | 0.500 | 0.501 | Scene-delta gate misses almost everything because visible targets persist with low frame-to-frame change. |
| Surveillance / MOT17Det | `fixed_skip_2` | 0.500 | 0.500 | Dense persistent crowd makes temporal skipping equivalent to sampling, not ROI-aware selection. |
| Retail / Mall | `stability_0_02_refresh_30` | 0.017 | 0.991 | Low threshold preserves recall but provides almost no workload reduction. Higher threshold loses many frames. |
| General / VisDrone | `fixed_skip_2` | 0.500 | 0.500 | Moving camera/small objects make simple temporal gating insufficient as a standalone policy. |

## Full Matrix Summary

| Dataset | Profile | Detector call reduction | Target-frame recall | Target-GT recall | Skipped target frames | Max target skip run |
|---|---|---:|---:|---:|---:|---:|
| Traffic | `process_all` | 0.000 | 1.000 | 1.000 | 0 | 0 |
| Traffic | `fixed_skip_2` | 0.500 | 0.500 | 0.497 | 60 | 1 |
| Traffic | `fixed_skip_5` | 0.800 | 0.200 | 0.200 | 96 | 4 |
| Traffic | `fixed_skip_10` | 0.900 | 0.100 | 0.097 | 108 | 9 |
| Traffic | `stability_0_01_refresh_30` | 0.467 | 0.533 | 0.523 | 56 | 9 |
| Traffic | `stability_0_02_refresh_30` | 0.942 | 0.058 | 0.050 | 113 | 29 |
| Traffic | `stability_0_05_refresh_30` | 0.967 | 0.033 | 0.030 | 116 | 29 |
| Logistics | `fixed_skip_2` | 0.500 | 0.500 | 0.501 | 60 | 1 |
| Logistics | `stability_0_01_refresh_30` | 0.967 | 0.033 | 0.036 | 116 | 29 |
| Surveillance | `fixed_skip_2` | 0.500 | 0.500 | 0.500 | 60 | 1 |
| Surveillance | `stability_0_01_refresh_30` | 0.967 | 0.033 | 0.033 | 116 | 29 |
| Retail | `stability_0_01_refresh_30` | 0.000 | 1.000 | 1.000 | 0 | 0 |
| Retail | `stability_0_02_refresh_30` | 0.017 | 0.983 | 0.991 | 2 | 2 |
| Retail | `stability_0_05_refresh_30` | 0.567 | 0.433 | 0.547 | 68 | 29 |
| VisDrone | `fixed_skip_2` | 0.500 | 0.500 | 0.500 | 60 | 1 |
| VisDrone | `stability_0_01_refresh_30` | 0.742 | 0.258 | 0.275 | 89 | 29 |

Full generated table:

- `outputs/temporal_gate_matrices/phase1_3_temporal_gate_20260916_152806/summary.md`

## Findings

1. Simple frame skipping is a cost knob, not a reliable ROI/gating policy, when target objects persist across most frames.
2. Scene-delta gating is highly domain-sensitive. It over-skips stable scenes with persistent targets and under-skips scenes whose entire image changes frequently.
3. Temporal gate can still be useful as a bounded-rate controller or fallback throttle, but not as the primary Phase 1.3 ROI generator.
4. The next candidate should move to spatial priors or memory-assisted policies, because “whether to process this frame at all” is too coarse for the selected samples.

## Verification

- `.venv/bin/python -m unittest tests.evaluation_tests.test_temporal_gate_report`
- `.venv/bin/python experiments/phase1_3/run_temporal_gate_matrix.py ...`

