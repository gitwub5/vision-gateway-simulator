# Phase 1.3-C Static Zone / Camera Prior POC - 2026-09-16

## Scope

Phase 1.3-C에서는 motion 없이도 카메라별로 항상 봐야 하는 영역이 있는지 확인했다.

이 run은 실제 배포 가능한 static ROI를 수동으로 그리는 단계가 아니라, GT 기반 oracle heatmap으로 static camera prior의 가능 상한선을 측정하는 POC다.

공통 조건:

- Frame limit: 120
- Grid: 32 x 18 cells
- Output root: `outputs/static_zone_prior_poc/`
- Matrix root: `outputs/static_zone_prior_matrices/phase1_3_static_zone_prior_20260916_155527`
- Profiles:
  - `top_05_center`
  - `top_10_center`
  - `top_20_center`
  - `top_30_center`
  - `top_10_dilate1`
  - `top_20_dilate1`
  - `top_30_dilate1`

## Implementation

Added:

- `evaluation/reports/static_zone_prior.py`
- `experiments/phase1_3/run_static_zone_prior_poc.py`
- `experiments/phase1_3/run_static_zone_prior_matrix.py`
- `tests/evaluation_tests/test_static_zone_prior_report.py`

Method:

1. Target GT bbox center를 32x18 grid cell에 누적한다.
2. 빈도가 높은 cell을 area budget별로 선택한다.
3. 선택된 cell을 그대로 쓰는 profile과 1-cell dilation을 적용한 profile을 비교한다.
4. Center containment와 bbox containment를 분리해서 평가한다.

## Matrix Runs

| Coverage Group | Run root |
|---|---|
| Traffic / parking | `outputs/static_zone_prior_poc/phase1_3_traffic_ua_detrac_mvi_39361_static_zone_prior_20260916_155527` |
| Logistics / smart factory | `outputs/static_zone_prior_poc/phase1_3_logistics_physicalai_row0709_after3m_static_zone_prior_20260916_155527` |
| Surveillance / security | `outputs/static_zone_prior_poc/phase1_3_surveillance_mot17_04_static_zone_prior_20260916_155527` |
| Retail / space analytics | `outputs/static_zone_prior_poc/phase1_3_retail_mall_dataset_static_zone_prior_20260916_155527` |
| General camera-motion stress | `outputs/static_zone_prior_poc/phase1_3_general_visdrone_uav0000086_static_zone_prior_20260916_155527` |

## Summary

Static camera prior is much stronger than the current motion/tile baseline in several domains. However, center recall and bbox recall diverge sharply. A static heatmap can identify where objects tend to be, but actual ROI crop needs expansion/dilation or another bbox-size model.

| Dataset | Strongest compact profile | Selected area | Center GT recall | BBox GT recall | Interpretation |
|---|---|---:|---:|---:|---|
| Traffic / UA-DETRAC | `top_10_center` | 0.101 | 1.000 | 0.000 | Vehicle centers are highly localized, but boxes are too large for center-only cells. |
| Logistics / PhysicalAI | `top_10_dilate1` | 0.260 | 1.000 | 0.813 | Strong static prior; dilation makes it usable as ROI seed. |
| Surveillance / MOT17Det | `top_10_dilate1` | 0.420 | 0.993 | 0.703 | Dense crowd zones are stable, but area cost is already large. |
| Retail / Mall | `top_20_dilate1` | 0.477 | 0.886 | 0.826 | Crowd distribution is broad; useful but not compact enough alone. |
| General / VisDrone | `top_20_dilate1` | 0.458 | 0.994 | 0.988 | Static prior is surprisingly strong in this selected moving-camera segment, likely because target distribution remains concentrated over the 120-frame window. |

## Full Matrix Pointer

Full generated table:

- `outputs/static_zone_prior_matrices/phase1_3_static_zone_prior_20260916_155527/summary.md`

## Findings

1. Static camera prior is a viable family for Phase 1.3. It outperforms simple temporal gate as a source of spatial selectivity.
2. Center heatmap alone is not enough for detector handoff. Bbox containment requires margin, dilation, or object-size-aware expansion.
3. PhysicalAI and VisDrone show the strongest static-prior potential in this 120-frame POC.
4. MOT17Det and Mall have stable target regions, but the active region becomes wide because people occupy broad crowd zones.
5. UA-DETRAC vehicle centers are very concentrated, but bbox containment remains poor even after 1-cell dilation. Traffic likely needs lane/road static ROI plus scale-aware expansion rather than center-cell ROI.

## Next Implication

Static prior should move forward as a candidate component, not as a final standalone policy:

- static zone + margin/dilation
- static zone + motion or objectness inside zone
- static zone + tracker memory
- domain-specific static ROI template for traffic/warehouse/retail

## Verification

- `.venv/bin/python -m unittest tests.evaluation_tests.test_static_zone_prior_report`
- `.venv/bin/python -m py_compile evaluation/reports/static_zone_prior.py experiments/phase1_3/run_static_zone_prior_poc.py experiments/phase1_3/run_static_zone_prior_matrix.py tests/evaluation_tests/test_static_zone_prior_report.py`
- `.venv/bin/python experiments/phase1_3/run_static_zone_prior_matrix.py ...`

