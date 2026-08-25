# ROI Proposal Validation

ROI proposal validation은 downstream model inference 없이 ROI 생성 품질과 입력 면적 절감을 확인한다.

Repo root에서 실행한다.

## PhysicalAI Person Crowded Quick

```bash
python experiments/run_roi_proposal_validation.py \
  --dataset-config configs/datasets/physicalai_row0709_after3m.yaml \
  --roi-generator-config configs/roi_generator/profile_tile_mask_recall_12x12.yaml \
  --experiment-name physicalai_tile_mask_recall_12x12 \
  --limit 120 \
  --render-limit 30
```

## PhysicalAI Hybrid Cost Quick

```bash
python experiments/run_roi_proposal_validation.py \
  --dataset-config configs/datasets/physicalai_row0709_after3m.yaml \
  --roi-generator-config configs/roi_generator/profile_hybrid_component_tile_cost.yaml \
  --experiment-name physicalai_hybrid_component_tile_cost \
  --limit 120 \
  --render-limit 30
```

## UA-DETRAC Vehicle Quick

```bash
python experiments/run_roi_proposal_validation.py \
  --dataset-config configs/datasets/ua_detrac_mvi_40204.yaml \
  --roi-generator-config configs/roi_generator/profile_balanced.yaml \
  --experiment-name uadetrac_mvi40204_component_bbox_balanced \
  --limit 120 \
  --render-limit 30
```

## Skip Visualization

빠른 metric 확인만 할 때:

```bash
python experiments/run_roi_proposal_validation.py \
  --dataset-config configs/datasets/physicalai_row0709_after3m.yaml \
  --roi-generator-config configs/roi_generator/profile_tile_mask_recall_12x12.yaml \
  --experiment-name physicalai_tile_mask_recall_12x12_no_viz \
  --limit 120 \
  --skip-visualization
```

## Outputs

```text
outputs/roi_proposal_validation/<run_id>/
  annotations/ground_truth.jsonl
  roi_metadata/rule_roi.jsonl
  roi_metadata/gate_decisions.jsonl
  roi_metadata/component_metadata.jsonl  # diagnostics-level=full only
  roi_metadata/tile_metadata.jsonl       # diagnostics-level=full only
  roi_metadata/policy_traces.jsonl       # diagnostics-level=full only
  reports/roi_proposal_report.json
  reports/roi_proposal_report.md
  reports/roi_policy_summary.md
  reports/cost_summary.json
  visualizations/
```

`component_metadata.jsonl`, `tile_metadata.jsonl`, `policy_traces.jsonl`은 기본 생성하지 않는다. 원인 분석이 필요한 run에서만 아래 옵션을 추가한다.

```bash
--diagnostics-level full
```

실행 결과 요약과 해석은 `docs/runs/`에 기록한다.
