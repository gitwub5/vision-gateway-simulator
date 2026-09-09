# Phase 1.3 Dataset Readiness Smoke

Date: 2026-09-09

Purpose: confirm that the selected Phase 1.3 datasets are locally available and connected to the canonical ROI proposal validation runner.

Command pattern:

```bash
python experiments/run_roi_proposal_validation.py \
  --dataset-config <config> \
  --run-id <run_id> \
  --limit 20 \
  --skip-visualization
```

Output root: `outputs/roi_proposal_validation/<run_id>/`

## Dataset Readiness

| Coverage Group | Dataset | Config | Local status |
|---|---|---|---|
| Traffic / parking | UA-DETRAC `MVI_39361` | `configs/datasets/ua_detrac/ua_detrac_mvi_39361.yaml` | ready |
| Logistics / smart factory | PhysicalAI `row0709_after3m` | `configs/datasets/physicalai/physicalai_row0709_after3m.yaml` | ready |
| Surveillance / security | MOTChallenge MOT17Det `MOT17-04` | `configs/datasets/motchallenge/mot17_04.yaml` | ready |
| Retail / space analytics | Mall Dataset | `configs/datasets/mall/mall_dataset.yaml` | ready |
| General stress | VisDrone-VID `uav0000086_00000_v` | `configs/datasets/visdrone/visdrone_vid_val_uav0000086.yaml` | ready |

AI City Challenge 2023 Track 4 was removed from Phase 1.3 because the useful GT portion is cropped synthetic product imagery, not a temporal CCTV-like sequence.

## Smoke Results

| Coverage Group | Dataset | Run ID | Frames | Target GT | ROI containment | Effective area reduction | Fallback rate | Full-frame check rate | No-ROI target frames | Final ROI area ratio |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Traffic / parking | UA-DETRAC MVI_39361 | `phase1_3_smoke_traffic_ua_detrac_mvi_39361` | 20 | 60 | 0.000 | 0.000 | 0.950 | 1.000 | 20 | 0.911 |
| Logistics / smart factory | PhysicalAI row0709_after3m | `phase1_3_smoke_logistics_physicalai_row0709_after3m` | 20 | 129 | 0.736 | 0.855 | 0.000 | 0.050 | 1 | 0.095 |
| Surveillance / security | MOT17Det MOT17-04 | `phase1_3_smoke_surveillance_mot17_04` | 20 | 842 | 0.030 | 0.033 | 0.900 | 0.950 | 19 | 0.529 |
| Retail / space analytics | Mall Dataset | `phase1_3_smoke_retail_mall_dataset` | 20 | 688 | 0.000 | 0.000 | 0.950 | 1.000 | 20 | 0.950 |
| General stress | VisDrone-VID uav0000086 | `phase1_3_smoke_general_visdrone_uav0000086` | 20 | 720 | 0.000 | 0.000 | 0.950 | 1.000 | 20 | 0.856 |

## Interpretation

The selected datasets are ready for Phase 1.3 execution. The current motion-primary ROI gate is only partially useful on the PhysicalAI indoor warehouse slice. It falls back to near-full-frame behavior or produces no usable target ROI on the other four domains.

This readiness run should be treated as a baseline failure signal, not a policy selection result. Phase 1.3 should compare candidate gate families against this baseline using:

- target GT ROI containment
- effective input area reduction
- fallback frame rate
- no-ROI target frame count
- small-object containment

VisDrone remains a camera-motion and small-object stress dataset. It should not be interpreted as representative fixed-CCTV deployment performance.
