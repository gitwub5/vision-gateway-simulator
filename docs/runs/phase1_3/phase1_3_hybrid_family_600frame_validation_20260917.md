# Phase 1.3-J/K Shortlisted Hybrid Family 600-Frame Validation

Date: 2026-09-17

## Scope

Phase 1.3-G에서 600-frame validation으로 올릴 두 hybrid 후보를 선정했다. 이 run은 두 후보를 실제로 구현하고, 대상 dataset에 대해 600-frame(또는 dataset이 제공하는 최대 프레임)으로 검증한다.

이 단계는 여전히 oracle detector refresh를 사용하는 PoC이며, non-oracle detector integration은 Phase 2 구현 범위로 남긴다.

## Implementation

추가한 구현:

- `evaluation/reports/static_tracker_temporal_hybrid.py`
- `evaluation/reports/static_lightweight_hybrid.py`
- `experiments/run_static_tracker_temporal_hybrid_poc.py`
- `experiments/run_static_lightweight_hybrid_poc.py`
- `tests/evaluation_tests/test_static_tracker_temporal_hybrid_report.py`
- `tests/evaluation_tests/test_static_lightweight_hybrid_report.py`

### Candidate 1: `static_zone_prior + tracker_memory + temporal_refresh_guard`

Static zone prior가 camera-specific spatial anchor로 항상 포함되고, tracker memory가 마지막 refresh(oracle GT) bbox를 margin과 함께 유지한다. `guard_stale_frames`가 memory를 신뢰할 수 있는 최대 staleness를 제한하는 temporal refresh guard 역할을 한다. Guard가 만료되면 memory 없이 static prior만으로 fallback한다(`guard_fallback`).

Profiles:

| Profile | static area | refresh interval | margin | guard(stale frames) |
|---|---:|---:|---:|---:|
| `static10_refresh5_margin30_guard5` | 0.10 | 5 | 0.30 | 5 |
| `static10_refresh10_margin50_guard10` | 0.10 | 10 | 0.50 | 10 |
| `static20_refresh10_margin50_guard5` | 0.20 | 10 | 0.50 | 5 |
| `static20_refresh15_margin50_guard10` | 0.20 | 15 | 0.50 | 10 |
| `static10_refresh5_margin50_guard3` | 0.10 | 5 | 0.50 | 3 |

### Candidate 2: `static_zone_prior + lightweight_visual_priority`

Static zone prior가 base ROI로 항상 선택되고, 남은 area budget(`extra_budget_ratio`)만큼 edge/texture/hybrid 신호에서 상위 cell을 추가로 선택한다. 최종 combined selection에 bbox-safe dilation을 적용할 수 있다.

Profiles:

| Profile | static area | signal | extra budget | combined dilation |
|---|---:|---|---:|---:|
| `static10_static_only` | 0.10 | hybrid | 0.00 | 0 |
| `static10_hybrid_budget10` | 0.10 | hybrid | 0.10 | 0 |
| `static10_hybrid_budget10_dilate1` | 0.10 | hybrid | 0.10 | 1 |
| `static20_hybrid_budget10_dilate1` | 0.20 | hybrid | 0.10 | 1 |
| `static10_edge_budget10_dilate1` | 0.10 | edge | 0.10 | 1 |
| `static10_texture_budget10_dilate1` | 0.10 | texture | 0.10 | 1 |

## Runs

| Candidate | Dataset | Frames | Run root |
|---|---|---:|---|
| static+tracker+guard | PhysicalAI | 600 | `outputs/static_tracker_temporal_hybrid_poc/phase1_3_logistics_physicalai_static_tracker_temporal_600_20260917` |
| static+tracker+guard | VisDrone | 464 (전체 시퀀스 길이, 600 요청 중 가용 최대) | `outputs/static_tracker_temporal_hybrid_poc/phase1_3_general_visdrone_static_tracker_temporal_600_20260917` |
| static+lightweight | Mall | 600 | `outputs/static_lightweight_hybrid_poc/phase1_3_retail_mall_static_lightweight_600_20260917` |
| static+lightweight | MOT17-04 | 600 | `outputs/static_lightweight_hybrid_poc/phase1_3_surveillance_mot17_static_lightweight_600_20260917` |

VisDrone `uav0000086_00000_v` 시퀀스는 464 frame만 존재해서 600-frame 요청이 자동으로 464로 제한됐다. 이는 dataset 한계이지 구현 오류가 아니다.

## Result: static_zone_prior + tracker_memory + temporal_refresh_guard

| Dataset | Profile | Static area | Full-frame call reduction | Effective input reduction | GT recall | Static-only memory recall | Guard fallback frames | ROI/memory frame |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| PhysicalAI | `static10_refresh10_margin50_guard10` | 0.222 | 0.900 | 0.695 | 0.976 | 0.015 | 0 | 132.8 |
| PhysicalAI | `static10_refresh5_margin30_guard5` | 0.222 | 0.800 | 0.621 | 0.981 | 0.016 | 0 | 132.8 |
| PhysicalAI | `static20_refresh10_margin50_guard5` | 0.370 | 0.900 | 0.565 | 0.601 | 0.015 | 240 | 215.7 |
| VisDrone | `static10_refresh5_margin30_guard5` | 0.306 | 0.800 | 0.498 | 0.936 | 0.019 | 0 | 225.6 |
| VisDrone | `static10_refresh10_margin50_guard10` | 0.306 | 0.899 | 0.534 | 0.902 | 0.019 | 0 | 225.5 |
| VisDrone | `static20_refresh10_margin50_guard5` | 0.479 | 0.899 | 0.450 | 0.597 | 0.033 | 184 | 303.7 |

Full table: `outputs/static_tracker_temporal_hybrid_poc/*/reports/static_tracker_temporal_hybrid_report.md`

## Result: static_zone_prior + lightweight_visual_priority

| Dataset | Profile | Combined area | Area reduction | BBox GT recall | Static-only BBox recall | Incremental from lightweight |
|---|---|---:|---:|---:|---:|---:|
| Mall | `static10_static_only` | 0.101 | 0.899 | 0.176 | 0.176 | 0.000 |
| Mall | `static10_hybrid_budget10_dilate1` | 0.532 | 0.468 | 0.797 | 0.176 | 0.621 |
| Mall | `static20_hybrid_budget10_dilate1` | 0.634 | 0.366 | 0.875 | 0.286 | 0.589 |
| MOT17-04 | `static10_static_only` | 0.101 | 0.899 | 0.082 | 0.082 | 0.000 |
| MOT17-04 | `static10_hybrid_budget10_dilate1` | 0.565 | 0.435 | 0.688 | 0.082 | 0.606 |
| MOT17-04 | `static20_hybrid_budget10_dilate1` | 0.739 | 0.261 | 0.813 | 0.144 | 0.668 |

Full table: `outputs/static_lightweight_hybrid_poc/*/reports/static_lightweight_hybrid_report.md`

## Interpretation

### Candidate 1 (PhysicalAI, VisDrone)

- 600-frame window에서도 tracker memory가 recall을 지배한다. Static prior 단독 recall은 두 dataset 모두 1.5-3.3% 수준으로 매우 약하다.
- Guard가 refresh interval보다 짧으면(`static20_refresh10_margin50_guard5`) memory가 자주 만료돼 static-only fallback이 자주 발생하고, static이 약하기 때문에 recall이 0.60 수준으로 붕괴한다. 즉 이 두 domain에서는 **guard는 refresh interval과 같거나 길어야 한다** — guard를 공격적으로 짧게 잡는 것은 이 조합에서 위험하다.
- Guard가 refresh interval 이상으로 유지되는 profile(`static10_refresh10_margin50_guard10`)은 두 dataset 모두 0.90 이상 recall과 0.5-0.7 effective input reduction을 유지한다. 이는 120-frame 결과(PhysicalAI 0.984/0.811, VisDrone 0.992/0.584)와 같은 방향이며, window가 길어져도 급격히 무너지지 않는다.
- 두 dataset 모두 ROI/memory frame이 130-300개로 높다. Non-oracle 구현 전에 ROI merge/packing이 필수라는 이전 결론이 600-frame에서도 유지된다.

### Candidate 2 (Mall, MOT17)

- Static prior만으로는 두 dataset 모두 bbox recall이 8-18% 수준으로 부족하다.
- Dilation 없는 budgeted lightweight 추가는 recall을 소폭만 개선한다(Mall 0.30, MOT17 0.14).
- Combined dilation을 적용하면 recall이 크게 개선된다(Mall 0.80-0.88, MOT17 0.69-0.81), 대신 selected area가 45-74%까지 커진다.
- Static area를 0.10에서 0.20으로 올리면 recall이 더 개선되지만(Mall +0.08, MOT17 +0.13) area reduction이 줄어든다. 두 dataset 모두 recall과 area 절감이 뚜렷한 tradeoff 곡선을 그린다.
- 이는 120-frame lightweight-only 결과(Mall `hybrid_top_20_dilate1` bbox 0.749, MOT17 0.464)보다 static prior 추가로 개선됐지만, 여전히 raw edge/texture dilation 방식은 area 비용이 크다.

## Findings

1. `static_zone_prior + tracker_memory + temporal_refresh_guard`는 PhysicalAI/VisDrone에서 600-frame으로도 high-confidence 후보를 유지한다. 단, guard는 refresh interval 이상으로 유지해야 한다.
2. `static_zone_prior + lightweight_visual_priority`는 Mall/MOT17에서 recall을 static-only 대비 크게 개선하지만(+0.59~+0.67), dilation 비용 때문에 medium-confidence로 유지한다. ROI/tile 기반 packing 또는 objectness 후속 신호가 필요하다.
3. 두 후보 모두 ROI count/packing이 non-oracle 구현 전 필수 선행 조건이다.

## Next Implication

- Candidate 1은 logistics/smart-factory와 general multi-class stress의 Phase 2 구현 대상으로 확정한다.
- Candidate 2는 surveillance/security와 retail/space analytics의 Phase 2 구현 대상으로 확정하되, dilation을 ROI/tile merge로 대체하는 개선이 우선 과제다.

## Verification

- `.venv/bin/python -m unittest tests.evaluation_tests.test_static_tracker_temporal_hybrid_report tests.evaluation_tests.test_static_lightweight_hybrid_report`
- `.venv/bin/python -m py_compile evaluation/reports/static_tracker_temporal_hybrid.py evaluation/reports/static_lightweight_hybrid.py experiments/run_static_tracker_temporal_hybrid_poc.py experiments/run_static_lightweight_hybrid_poc.py tests/evaluation_tests/test_static_tracker_temporal_hybrid_report.py tests/evaluation_tests/test_static_lightweight_hybrid_report.py`
- `.venv/bin/python experiments/run_static_tracker_temporal_hybrid_poc.py --dataset-config configs/datasets/physicalai/physicalai_row0709_after3m.yaml --limit 600 ...`
- `.venv/bin/python experiments/run_static_tracker_temporal_hybrid_poc.py --dataset-config configs/datasets/visdrone/visdrone_vid_val_uav0000086.yaml --limit 600 ...`
- `.venv/bin/python experiments/run_static_lightweight_hybrid_poc.py --dataset-config configs/datasets/mall/mall_dataset.yaml --limit 600 ...`
- `.venv/bin/python experiments/run_static_lightweight_hybrid_poc.py --dataset-config configs/datasets/motchallenge/mot17_04.yaml --limit 600 ...`
