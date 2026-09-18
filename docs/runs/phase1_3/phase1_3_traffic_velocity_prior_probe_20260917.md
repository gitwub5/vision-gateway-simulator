# Phase 1.3-H Traffic Velocity / Scale Prior Probe

Date: 2026-09-17

## Scope

Phase 1.3-G에서 Traffic / UA-DETRAC은 기존 hybrid 후보로 바로 올리기 어렵다고 판정했다. 이 probe는 traffic 전용 후보였던 `lane_or_scale_prior + velocity_tracker` 중, 먼저 `velocity_tracker + scale-aware margin`이 단순 hold-memory보다 개선되는지 확인한다.

이 단계는 실제 Kalman filter 구현이 아니라, oracle detector refresh 사이에서 이전 두 refresh bbox를 이용해 선형 속도 예측을 수행하는 lightweight probe다.

## Implementation

추가한 구현:

- `evaluation/reports/velocity_prior_tracker.py`
- `experiments/run_velocity_prior_tracker_poc.py`
- `tests/evaluation_tests/test_velocity_prior_tracker_report.py`

Profile:

| Profile | 의미 |
|---|---|
| `hold_refresh_5_margin_30` | 기존 hold-memory 비교 기준 |
| `velocity_refresh_5_margin_30` | refresh bbox 간 선형 속도 예측 |
| `velocity_refresh_5_margin_50` | 속도 예측 + 더 큰 margin |
| `velocity_scale_refresh_5_margin_30` | 속도 예측 + small object scale-aware margin |
| `velocity_scale_refresh_10_margin_50` | 더 긴 refresh interval에서 속도/scale margin 적용 |

## Runs

| Run | Frames | Output |
|---|---:|---|
| `phase1_3_traffic_velocity_prior_120_20260917` | 120 | `outputs/velocity_prior_tracker_poc/phase1_3_traffic_velocity_prior_120_20260917` |
| `phase1_3_traffic_velocity_prior_600_20260917` | 600 | `outputs/velocity_prior_tracker_poc/phase1_3_traffic_velocity_prior_600_20260917` |

## 120-frame Result

| Profile | Detector call reduction | Effective input reduction | GT recall | Memory-frame GT recall |
|---|---:|---:|---:|---:|
| `hold_refresh_5_margin_30` | 0.800 | 0.645 | 0.616 | 0.520 |
| `velocity_refresh_5_margin_30` | 0.800 | 0.645 | 0.616 | 0.520 |
| `velocity_refresh_5_margin_50` | 0.800 | 0.589 | 0.616 | 0.520 |
| `velocity_scale_refresh_5_margin_30` | 0.800 | 0.638 | 0.616 | 0.520 |
| `velocity_scale_refresh_10_margin_50` | 0.900 | 0.661 | 0.543 | 0.493 |

## 600-frame Result

| Profile | Detector call reduction | Effective input reduction | GT recall | Memory-frame GT recall |
|---|---:|---:|---:|---:|
| `hold_refresh_5_margin_30` | 0.800 | 0.645 | 0.624 | 0.528 |
| `velocity_refresh_5_margin_30` | 0.800 | 0.646 | 0.622 | 0.527 |
| `velocity_refresh_5_margin_50` | 0.800 | 0.590 | 0.624 | 0.528 |
| `velocity_scale_refresh_5_margin_30` | 0.800 | 0.634 | 0.623 | 0.527 |
| `velocity_scale_refresh_10_margin_50` | 0.900 | 0.651 | 0.569 | 0.520 |

## Interpretation

단순 velocity prediction은 UA-DETRAC traffic에서 hold-memory를 개선하지 못했다.

120-frame과 600-frame 결과가 같은 방향을 보인다.

- `velocity_refresh_5_margin_30`은 hold-memory와 거의 동일하거나 약간 낮다.
- margin을 0.50으로 키워도 recall은 개선되지 않고 input reduction만 악화된다.
- scale-aware margin도 recall 개선이 거의 없다.
- refresh interval을 10으로 늘리면 detector call reduction은 90%까지 올라가지만 recall은 57% 수준으로 떨어진다.

이는 Traffic failure가 단순히 "이미 본 차량의 이동 위치를 못 맞추는 문제"만은 아니라는 뜻이다. 더 큰 문제는 refresh 사이에 새로 진입하는 차량, lane/road region의 넓은 이동 경로, perspective에 따른 bbox scale 변화다.

## Decision

Traffic 후보를 `velocity_tracker` 단독으로 600-frame validation shortlist에 올리지 않는다.

다음 traffic probe는 아래 방향이어야 한다.

- lane/road-region prior 또는 roadway envelope
- perspective/scale-aware expansion map
- object-size bucket별 margin
- detector refresh 사이 새 객체 진입을 커버하는 static lane prior
- 필요 시 Kalman filter는 lane/scale prior 위의 tracker 보조로만 사용

즉, 1.3-G의 `lane_or_scale_prior + velocity_tracker` 후보는 유지하지만, 우선순위는 velocity가 아니라 lane/scale prior 쪽이다.

## Verification

- `python -m unittest tests.evaluation_tests.test_velocity_prior_tracker_report`
- `python -m py_compile evaluation/reports/velocity_prior_tracker.py experiments/run_velocity_prior_tracker_poc.py tests/evaluation_tests/test_velocity_prior_tracker_report.py`
- `python experiments/run_velocity_prior_tracker_poc.py --dataset-config configs/datasets/ua_detrac/ua_detrac_mvi_39361.yaml --limit 120`
- `python experiments/run_velocity_prior_tracker_poc.py --dataset-config configs/datasets/ua_detrac/ua_detrac_mvi_39361.yaml --limit 600`
