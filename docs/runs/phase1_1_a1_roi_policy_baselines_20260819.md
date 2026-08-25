# Phase 1.1 A1 ROI Policy Baselines

## Scope

Phase 1.1 A1의 목적은 `component_bbox`, `tile_mask`, `hybrid_component_tile`을 같은 ROI proposal metric으로 비교하고, 다음 tuning 대상으로 남길 profile을 고르는 것이다.

## Datasets

| Dataset | Segment | Config | Target |
|---|---|---|---|
| PhysicalAI Smart Spaces row 709 | `Warehouse_000/Camera_0002` f5400-5519 | `configs/datasets/physicalai/physicalai_row0709_after3m.yaml` | `person` |
| UA-DETRAC | `MVI_40204` f0000-0119 | `configs/datasets/ua_detrac/ua_detrac_mvi_40204.yaml` | `car`, `bus`, `truck` |

## A1 Matrix

| Dataset | Profile | Policy | GT | ROI contain | Tile contain | Missed | No ROI frames | ROI/frame | Tile/frame | Eff. reduction | Fallback |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PhysicalAI after3m | `component_bbox_balanced` | `component_bbox` | 699 | 0.618 | 0.127 | 267 | 1 | 1.43 | 36.76 | 0.898 | 0.000 |
| PhysicalAI after3m | `component_bbox_highres` | `component_bbox` | 699 | 0.599 | 0.129 | 280 | 1 | 1.36 | 40.27 | 0.898 | 0.000 |
| PhysicalAI after3m | `component_bbox_noise_filter` | `component_bbox` | 699 | 0.476 | 0.127 | 366 | 1 | 1.47 | 36.76 | 0.922 | 0.000 |
| PhysicalAI after3m | `component_bbox_recall_padding` | `component_bbox` | 699 | 0.017 | 0.129 | 687 | 118 | 0.05 | 49.31 | 0.008 | 0.975 |
| PhysicalAI after3m | `tile_mask_balanced` | `tile_mask` | 699 | 0.644 | 0.117 | 249 | 4 | 1.42 | 6.40 | 0.840 | 0.025 |
| PhysicalAI after3m | `hybrid_component_tile_balanced` | `hybrid_component_tile` | 699 | 0.615 | 0.117 | 269 | 1 | 1.41 | 6.40 | 0.899 | 0.000 |
| UA-DETRAC MVI_40204 | `component_bbox_balanced` | `component_bbox` | 1704 | 0.000 | 0.288 | 1704 | 120 | 0.00 | 53.79 | 0.000 | 0.992 |
| UA-DETRAC MVI_40204 | `component_bbox_highres` | `component_bbox` | 1704 | 0.000 | 0.286 | 1704 | 120 | 0.00 | 62.71 | 0.000 | 0.992 |
| UA-DETRAC MVI_40204 | `component_bbox_noise_filter` | `component_bbox` | 1704 | 0.000 | 0.288 | 1704 | 120 | 0.00 | 53.79 | 0.000 | 0.992 |
| UA-DETRAC MVI_40204 | `component_bbox_recall_padding` | `component_bbox` | 1704 | 0.000 | 0.288 | 1704 | 120 | 0.00 | 62.28 | 0.000 | 0.992 |
| UA-DETRAC MVI_40204 | `tile_mask_balanced` | `tile_mask` | 1704 | 0.009 | 0.288 | 1688 | 119 | 0.03 | 39.66 | 0.005 | 0.983 |
| UA-DETRAC MVI_40204 | `hybrid_component_tile_balanced` | `hybrid_component_tile` | 1704 | 0.000 | 0.288 | 1704 | 120 | 0.00 | 39.66 | 0.000 | 0.992 |

## Tile/Hybrid Sweep

PhysicalAI after3m에서 tile/hybrid의 grid size와 tile activity threshold를 비교했다.

| Policy | Grid | Threshold | ROI contain | Missed | No ROI frames | ROI/frame | Tile/frame | Eff. reduction | Fallback |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `hybrid_component_tile` | 8x8 | 0.005 | 0.618 | 267 | 1 | 1.43 | 9.68 | 0.898 | 0.000 |
| `hybrid_component_tile` | 12x12 | 0.010 | 0.618 | 267 | 1 | 1.43 | 13.54 | 0.898 | 0.000 |
| `hybrid_component_tile` | 8x8 | 0.010 | 0.615 | 269 | 1 | 1.41 | 6.40 | 0.899 | 0.000 |
| `hybrid_component_tile` | 8x8 | 0.020 | 0.585 | 290 | 1 | 1.41 | 4.90 | 0.906 | 0.000 |
| `hybrid_component_tile` | 6x6 | 0.010 | 0.574 | 298 | 1 | 1.39 | 4.41 | 0.907 | 0.000 |
| `tile_mask` | 12x12 | 0.010 | 0.758 | 169 | 5 | 2.38 | 13.54 | 0.810 | 0.033 |
| `tile_mask` | 6x6 | 0.010 | 0.722 | 194 | 4 | 1.18 | 4.41 | 0.776 | 0.025 |
| `tile_mask` | 8x8 | 0.005 | 0.674 | 228 | 14 | 2.17 | 9.68 | 0.682 | 0.108 |
| `tile_mask` | 8x8 | 0.010 | 0.644 | 249 | 4 | 1.42 | 6.40 | 0.840 | 0.025 |
| `tile_mask` | 8x8 | 0.020 | 0.479 | 364 | 3 | 1.48 | 4.90 | 0.891 | 0.017 |

## Selected Profiles

| Profile | Role | Run ID | ROI contain | Missed | ROI/frame | Tile/frame | Eff. reduction | Fallback |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `tile_mask_recall_12x12` | recall-oriented tile profile | `a1_physicalai_tile_mask_recall_12x12_f5400_120` | 0.758 | 169 | 2.383 | 13.542 | 0.810 | 0.033 |
| `hybrid_component_tile_cost` | cost-oriented hybrid profile | `a1_physicalai_hybrid_component_tile_cost_f5400_120` | 0.618 | 267 | 1.425 | 9.675 | 0.898 | 0.000 |

## 600-Frame Recheck

Before this recheck, existing `outputs/roi_proposal_validation/` contents were cleared.

PhysicalAI after3m was rerun for 600 frames to check whether the 120-frame trend holds over a longer segment.

| Profile | Policy | Run ID | GT | ROI contain | Tile contain | Missed | No ROI frames | ROI/frame | Tile/frame | Eff. reduction | Fallback | Avg latency ms |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `component_bbox_balanced` | `component_bbox` | `a1_600_physicalai_component_bbox_balanced_f5400_600` | 2879 | 0.441 | 0.080 | 1610 | 1 | 1.47 | 36.83 | 0.923 | 0.000 | 2.032 |
| `tile_mask_recall_12x12` | `tile_mask` | `a1_600_physicalai_tile_mask_recall_12x12_f5400_600` | 2879 | 0.544 | 0.021 | 1312 | 21 | 2.64 | 12.75 | 0.855 | 0.033 | 1.676 |
| `hybrid_component_tile_cost` | `hybrid_component_tile` | `a1_600_physicalai_hybrid_component_tile_cost_f5400_600` | 2879 | 0.440 | 0.074 | 1611 | 1 | 1.47 | 9.62 | 0.924 | 0.000 | 2.022 |

The 600-frame result keeps the same broad direction as the 120-frame run, but the absolute containment drops for all profiles. `tile_mask_recall_12x12` still improves containment over component baseline, from 0.441 to 0.544, while spending more ROI area. `hybrid_component_tile_cost` remains nearly identical to component baseline in containment and effective input reduction, but reduces selected tile count.

## Interpretation

`tile_mask_recall_12x12` is the best A1 recall candidate on PhysicalAI after3m. In the 120-frame run it improves ROI containment from the component baseline 0.618 to 0.758, but it spends more selected tiles and lowers effective input area reduction to 0.810. In the 600-frame recheck the absolute containment drops for all policies, but tile_mask keeps a clear advantage over component_bbox: 0.544 vs 0.441 ROI containment.

`hybrid_component_tile_cost` keeps roughly the same ROI containment as component baseline while preserving high effective input area reduction and avoiding fallback. On the 600-frame run it does not improve ROI containment, but it reduces selected tile metadata from 36.83 tiles/frame to 9.62 tiles/frame while keeping effective reduction nearly unchanged. This makes it a cost-observability/control candidate, not a recall candidate.

`component_bbox_noise_filter` reduces area but loses too much containment. `component_bbox_recall_padding` is invalid under the current area budget because fallback becomes dominant.

`UA-DETRAC MVI_40204` should be treated as a dense-scene/fallback diagnostic for now. The scene is vehicle-only and label-clean, but current motion-based profiles select too much area and fall back almost every frame.

## Visual Review

Latest comparison visualization:

```text
outputs/roi_proposal_validation/a1_compare_visual_policy_methods_f5401_100/
```

Representative frame:

```text
outputs/roi_proposal_validation/a1_compare_visual_policy_methods_f5401_100/Camera_0002_f005401_policy_methods.jpg
```

Visual review confirms the metric direction:

- `component_bbox_balanced` shows only final ROI. Its ROI is compact, but it repeatedly misses distant/small person boxes when motion components merge around a nearer subject.
- `tile_mask_recall_12x12` shows selected tiles plus final ROI. It expands over active tile groups and includes more distant/small person boxes, but this comes from larger rectangular ROI groups and still misses some low-motion or edge targets.
- `hybrid_component_tile_cost` shows selected tiles plus final ROI, but final ROI mostly tracks component_bbox because the current hybrid policy only gates component candidates by tile overlap. It does not create tile-first recall ROIs.
- The visualization is policy-discriminative enough for A1: common gray/heatmap/motion preprocessing is not the focus; the visible difference is final ROI shape plus selected tiles for tile/hybrid policies.

## A1 Decision

| Profile | Decision | Reason |
|---|---|---|
| `component_bbox_balanced` | Keep as baseline | Stable compact baseline, but not enough recall on PhysicalAI after3m. |
| `tile_mask_recall_12x12` | Keep/Tune | Best A1 recall profile. It improves 600-frame ROI containment by +0.103 over component_bbox, at the cost of more ROI area, more ROI/frame, and 3.3% fallback. |
| `hybrid_component_tile_cost` | Keep as cost candidate | Does not improve recall, but preserves component_bbox containment/effective reduction while reducing selected tile count. Carry forward only as a budget/control candidate. |
| `component_bbox_noise_filter` | Disable for now | Area reduction loses too much containment. |
| `component_bbox_recall_padding` | Disable for now | Current budget makes fallback dominant. |
| `UA-DETRAC current profiles` | Diagnostic only | Dense vehicle scene causes near-total fallback/no-ROI behavior; do not use it to pick A1 winner. |

## Remaining Work

No additional A1 baseline experiment is required before moving to the next policy question. The 120-frame sweep, 600-frame recheck, and policy-method visualization agree on the direction.

Recommended next step:

1. Move to A2 budget/cost policy using `tile_mask_recall_12x12` as the recall candidate and `hybrid_component_tile_cost` as the cost-control candidate.
2. Keep `component_bbox_balanced` as the comparison baseline.
3. Defer small/edge target miss reduction to Stage B, because the remaining tile_mask misses are not solved by the current component-gated hybrid implementation.
