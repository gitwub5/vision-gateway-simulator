# ROI Proposal Validation

ROI proposal validation은 downstream model inference 없이 ROI 생성 품질과 입력 면적 절감을 확인한다.

Repo root에서 실행한다.

## PhysicalAI Person Crowded Quick

```bash
python experiments/run_roi_proposal_validation.py \
  --dataset-config configs/datasets/physicalai/physicalai_row0709_after3m.yaml \
  --roi-generator-config configs/roi_generator/phase1_1/tile/profile_tile_mask_recall_12x12.yaml \
  --experiment-name physicalai_tile_mask_recall_12x12 \
  --limit 120 \
  --render-limit 30
```

## PhysicalAI Hybrid Cost Quick

```bash
python experiments/run_roi_proposal_validation.py \
  --dataset-config configs/datasets/physicalai/physicalai_row0709_after3m.yaml \
  --roi-generator-config configs/roi_generator/phase1_1/hybrid/profile_hybrid_component_tile_cost.yaml \
  --experiment-name physicalai_hybrid_component_tile_cost \
  --limit 120 \
  --render-limit 30
```

## UA-DETRAC Vehicle Quick

```bash
python experiments/run_roi_proposal_validation.py \
  --dataset-config configs/datasets/ua_detrac/ua_detrac_mvi_40204.yaml \
  --roi-generator-config configs/roi_generator/legacy/profile_balanced.yaml \
  --experiment-name uadetrac_mvi40204_component_bbox_balanced \
  --limit 120 \
  --render-limit 30
```

## Skip Visualization

빠른 metric 확인만 할 때:

```bash
python experiments/run_roi_proposal_validation.py \
  --dataset-config configs/datasets/physicalai/physicalai_row0709_after3m.yaml \
  --roi-generator-config configs/roi_generator/phase1_1/tile/profile_tile_mask_recall_12x12.yaml \
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
  roi_metadata/tile_metadata.jsonl       # diagnostics-level=tile_trace or full
  roi_metadata/policy_traces.jsonl       # diagnostics-level=full only
  reports/roi_proposal_report.json
  reports/roi_proposal_report.md
  reports/roi_policy_summary.md
  reports/cost_summary.json
  visualizations/
```

기본 `minimal`은 frame/ROI metadata만 기록한다. Phase 1.2 공식 run의 tier는
`configs/experiments/*.yaml`에서 선택하고 matrix runner가 전달한다. 단일-run CLI 옵션은
ad-hoc sweep과 디버깅 용도로만 사용한다. Phase 1.2 tile 판단용 run은 tile 위치만 추가하는
경량 tier를 사용한다.

```bash
--diagnostics-level tile_trace
```

component와 전체 policy trace까지 필요한 상세 디버깅에서는 아래 tier를 사용한다.

```bash
--diagnostics-level full
```

## Compare Compatible Runs

동일 dataset segment와 target class로 실행한 ROI proposal run을 비교한다. Manifest의 resolved segment가 다르면 비교를 중단한다.

```bash
python tools/summarize_roi_proposal_runs.py \
  --run baseline=outputs/roi_proposal_validation/<baseline_run_id> \
  --run candidate=outputs/roi_proposal_validation/<candidate_run_id> \
  --output-markdown outputs/roi_proposal_validation/<comparison_id>/summary.md \
  --output-json outputs/roi_proposal_validation/<comparison_id>/summary.json
```

`ground_truth` feedback은 oracle upper bound, `full_frame_yolo` feedback은 actual detector run으로 manifest에 구분된다.

실행 결과 요약과 해석은 `docs/runs/`에 기록한다.
