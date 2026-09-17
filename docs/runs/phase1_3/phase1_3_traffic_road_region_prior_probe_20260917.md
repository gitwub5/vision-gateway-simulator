# Phase 1.3-I Traffic Road / Lane Region Prior Probe

Date: 2026-09-17

## Scope

Traffic velocity probe에서 단순 velocity prediction이 hold-memory를 개선하지 못했다. 이 probe는 다음 가설을 확인한다.

```text
Traffic ROI는 개별 차량 velocity보다 road/lane region prior가 먼저 필요하다.
```

현재는 lane annotation이 없으므로, GT bbox 분포에서 row별 x-range를 만든 oracle road envelope를 사용한다. 이는 production 방식이 아니라, road/lane prior가 실험할 가치가 있는지 확인하는 feasibility check다.

## Implementation

추가한 구현:

- `evaluation/reports/road_region_prior.py`
- `experiments/run_road_region_prior_poc.py`
- `tests/evaluation_tests/test_road_region_prior_report.py`

Profile:

| Profile | 의미 |
|---|---|
| `bbox_envelope_margin_0` | GT bbox가 지나간 row별 x-range를 그대로 road envelope로 사용 |
| `bbox_envelope_margin_1` | row별 x-range에 x margin 1 cell 추가 |
| `bbox_envelope_margin_2` | x margin 2 cell, y dilation 1 cell |
| `bbox_envelope_margin_3` | x margin 3 cell, y dilation 1 cell |
| `center_envelope_margin_2` | bbox가 아니라 center 분포만 사용한 lighter envelope |

## Runs

| Run | Frames | Output |
|---|---:|---|
| `phase1_3_traffic_road_region_prior_120_20260917` | 120 | `outputs/road_region_prior_poc/phase1_3_traffic_road_region_prior_120_20260917` |
| `phase1_3_traffic_road_region_prior_600_20260917` | 600 | `outputs/road_region_prior_poc/phase1_3_traffic_road_region_prior_600_20260917` |

## 120-frame Result

| Profile | Selected area | Input reduction | Center recall | BBox recall |
|---|---:|---:|---:|---:|
| `bbox_envelope_margin_0` | 0.316 | 0.684 | 1.000 | 1.000 |
| `bbox_envelope_margin_1` | 0.339 | 0.661 | 1.000 | 1.000 |
| `bbox_envelope_margin_2` | 0.488 | 0.512 | 1.000 | 1.000 |
| `bbox_envelope_margin_3` | 0.505 | 0.495 | 1.000 | 1.000 |
| `center_envelope_margin_2` | 0.271 | 0.729 | 1.000 | 0.499 |

## 600-frame Result

| Profile | Selected area | Input reduction | Center recall | BBox recall |
|---|---:|---:|---:|---:|
| `bbox_envelope_margin_0` | 0.646 | 0.354 | 1.000 | 1.000 |
| `bbox_envelope_margin_1` | 0.655 | 0.345 | 1.000 | 1.000 |
| `bbox_envelope_margin_2` | 0.736 | 0.264 | 1.000 | 1.000 |
| `bbox_envelope_margin_3` | 0.740 | 0.260 | 1.000 | 1.000 |
| `center_envelope_margin_2` | 0.620 | 0.380 | 1.000 | 0.836 |

## Interpretation

Road/lane-style prior fixes the bbox containment issue, but the selected area grows quickly as the observed time window grows.

Important contrast:

- 120-frame `bbox_envelope_margin_0`: full bbox recall at 31.6% area.
- 600-frame `bbox_envelope_margin_0`: full bbox recall at 64.6% area.

This means traffic has a stronger spatial prior than motion/tile or simple tracker, but a naive whole-road envelope becomes too broad for long windows.

The useful direction is not "one static road ROI" but:

- road/lane prior split into smaller lane segments
- entry/exit zone coverage for newly entering vehicles
- perspective/scale-aware expansion by row or lane
- detector refresh/tracker only inside lane segments
- packing/budget layer to decide which lane segments are active

## Decision

Traffic should not be excluded from Phase 1.3, but it should not share the same hybrid candidate as PhysicalAI/Mall/MOT.

Traffic candidate becomes:

```text
road/lane segmented prior + entry-zone guard + tracker/refresh inside active lane segments
```

This is a distinct candidate family from:

- `static_zone_prior + tracker_memory + temporal_refresh_guard`
- `static_zone_prior + lightweight_visual_priority`

## Phase 1.3 Finish Implication

This probe is enough to decide the Phase 1.3 traffic direction. The next traffic work should be implementation-oriented, not more broad exploration:

- implement lane/road segmented prior
- evaluate 600-frame with ROI budget and packing
- compare against full road envelope and current static top-cell prior

That belongs either to the last Phase 1.3 validation pass or early Phase 2 implementation, depending on how narrow the next step is.

## Verification

- `python -m unittest tests.evaluation_tests.test_road_region_prior_report`
- `python -m py_compile evaluation/reports/road_region_prior.py experiments/run_road_region_prior_poc.py tests/evaluation_tests/test_road_region_prior_report.py`
- `python experiments/run_road_region_prior_poc.py --dataset-config configs/datasets/ua_detrac/ua_detrac_mvi_39361.yaml --limit 120`
- `python experiments/run_road_region_prior_poc.py --dataset-config configs/datasets/ua_detrac/ua_detrac_mvi_39361.yaml --limit 600`
