# Phase 1.3-D Feedback / Tracker Memory POC - 2026-09-17

## Scope

Phase 1.3-D에서는 full-frame detector를 매 프레임 실행하지 않고, 주기적으로만 refresh한 뒤 이전 bbox를 ROI memory로 재사용하는 방식의 가능 상한선을 확인했다.

이 run은 실제 tracker 구현 품질을 측정하는 단계가 아니다. GT bbox를 detector refresh 결과로 간주하는 oracle POC이며, 질문은 다음에 가깝다.

```text
이전 detector 결과를 일정 시간 유지해서 ROI로 재사용하면
full-frame detector 호출과 입력 면적을 얼마나 줄이면서 recall을 유지할 수 있는가?
```

공통 조건:

- Frame limit: 120
- Output root: `outputs/tracker_memory_poc/`
- Matrix root: `outputs/tracker_memory_matrices/phase1_3_tracker_memory_20260917_103714`
- Refresh frame: full-frame detector call로 간주
- Memory frame: 마지막 refresh bbox에 margin을 붙인 ROI만 입력으로 간주
- Profiles:
  - `refresh_2_margin_30`
  - `refresh_5_margin_30`
  - `refresh_10_margin_30`
  - `refresh_15_margin_30`
  - `refresh_5_margin_50`
  - `refresh_10_margin_50`

## Implementation

Added:

- `evaluation/reports/tracker_memory.py`
- `experiments/run_tracker_memory_poc.py`
- `experiments/run_tracker_memory_matrix.py`
- `tests/evaluation_tests/test_tracker_memory_report.py`

The runner reuses existing dataset loaders and annotation loaders. It records per-frame memory ROI count, containment, refresh state, and estimated effective input area.

## Matrix Runs

| Coverage Group | Run root |
|---|---|
| Traffic / parking | `outputs/tracker_memory_poc/phase1_3_traffic_ua_detrac_mvi_39361_tracker_memory_20260917_103714` |
| Logistics / smart factory | `outputs/tracker_memory_poc/phase1_3_logistics_physicalai_row0709_after3m_tracker_memory_20260917_103714` |
| Surveillance / security | `outputs/tracker_memory_poc/phase1_3_surveillance_mot17_04_tracker_memory_20260917_103714` |
| Retail / space analytics | `outputs/tracker_memory_poc/phase1_3_retail_mall_dataset_tracker_memory_20260917_103714` |
| General camera-motion stress | `outputs/tracker_memory_poc/phase1_3_general_visdrone_uav0000086_tracker_memory_20260917_103714` |

## Summary

Tracker memory is highly domain-sensitive. It is strong when targets move slowly relative to bbox size and camera motion is modest. It is weak when object positions change too much between refreshes or when dense scenes create too many memory ROIs.

| Dataset | Useful profile | Full-frame call reduction | Effective input reduction | GT recall | Interpretation |
|---|---|---:|---:|---:|---|
| Traffic / UA-DETRAC | `refresh_2_margin_30` | 0.500 | 0.403 | 0.754 | Hold-only memory is not enough for vehicles in this unstable segment. |
| Logistics / PhysicalAI | `refresh_10_margin_50` | 0.900 | 0.811 | 0.984 | Strong candidate. Worker motion is predictable enough for memory ROI. |
| Surveillance / MOT17Det | `refresh_5_margin_30` | 0.800 | 0.507 | 0.839 | Recall is acceptable, but ROI count is very high in dense crowd scenes. |
| Retail / Mall | `refresh_2_margin_30` | 0.500 | 0.407 | 0.743 | Crowd flow and point-proxy targets move too much for simple hold memory. |
| General / VisDrone | `refresh_5_margin_50` | 0.800 | 0.584 | 0.992 | Strong in this selected segment, but uses many ROIs and should be interpreted as oracle upper bound. |

## Full Matrix Pointer

Full generated table:

- `outputs/tracker_memory_matrices/phase1_3_tracker_memory_20260917_103714/summary.md`

## Findings

1. Feedback/tracker memory is a viable candidate family for logistics/smart-factory and some multi-class camera segments.
2. PhysicalAI shows the best cost/recall balance: `refresh_10_margin_50` keeps 0.984 GT recall with 0.811 effective input area reduction.
3. VisDrone also looks strong in this 120-frame oracle run, but because the camera is not fixed and ROI count is high, this needs non-oracle validation before promotion.
4. MOT17Det shows that memory can preserve recall in dense scenes, but ROI count around 41 per memory frame makes packing/batching cost a concern.
5. UA-DETRAC and Mall indicate that simple bbox hold is insufficient for traffic vehicles and broad retail crowd flow. These need velocity prediction, scene prior, or detector refresh at shorter intervals.

## Next Implication

Carry tracker memory forward as a component, not as a universal standalone gate:

- logistics: tracker memory + static zone is a strong hybrid candidate
- surveillance: tracker memory needs ROI budget/merge/packing constraints
- traffic: needs motion/velocity or lane-aware prediction
- retail: needs broader static zone/flow prior rather than individual bbox hold
- VisDrone/general: needs camera-motion compensation or lower-cost objectness validation

## Verification

- `.venv/bin/python -m unittest tests.evaluation_tests.test_tracker_memory_report`
- `.venv/bin/python -m py_compile evaluation/reports/tracker_memory.py experiments/run_tracker_memory_poc.py experiments/run_tracker_memory_matrix.py tests/evaluation_tests/test_tracker_memory_report.py`
- `.venv/bin/python experiments/run_tracker_memory_matrix.py ...`

