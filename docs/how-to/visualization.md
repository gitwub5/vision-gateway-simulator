# ROI Visualization Workflows

ROI proposal 시각화는 목적에 따라 debug, review, compare 세 workflow로 구분한다.

## 1. Generation Debug

한 실험의 ROI 생성 내부 과정에서 motion, tile/component 후보, merge, feedback, final ROI를 확인할 때 사용한다.

```bash
python experiments/run_roi_proposal_validation.py \
  --dataset-config configs/datasets/physicalai/physicalai_row0709_after3m.yaml \
  --roi-generator-config configs/roi_generator/phase1_1/tile/profile_tile_mask_recall_12x12.yaml \
  --experiment-name tile_debug \
  --limit 30 \
  --diagnostics-level full \
  --render-roi-debug-all \
  --render-roi-debug-limit 10
```

출력:

```text
<run_root>/visualizations/debug/generation/
```

Generation debug는 실행 중 `RoiDebugSnapshot`이 필요하므로 `full` diagnostics에서만 활성화된다.

## 2. Single Run Review

이미 완료한 ROI proposal run의 final ROI, 실제 selected tile, GT containment, failure frame을 다시 확인할 때 사용한다.

```bash
python tools/render_roi_run.py \
  --run-root outputs/roi_proposal_validation/<run_id> \
  --view all \
  --preset missed \
  --max-frames 80
```

특정 frame만 확인:

```bash
python tools/render_roi_run.py \
  --run-root outputs/roi_proposal_validation/<run_id> \
  --frame 5429 \
  --frame 5512
```

출력:

```text
<run_root>/visualizations/review/
  roi_overlay/
  containment/
  failures/
  manifest.json
```

Tile trace가 없는 run은 ROI에서 tile을 역추정하지 않고 unavailable로 표시한다.

## 3. Multi Run Comparison

동일 dataset segment와 target class로 실행한 둘 이상의 run을 같은 frame에서 비교할 때 사용한다.

```bash
python tools/compare_roi_runs.py \
  --run baseline=outputs/roi_proposal_validation/<baseline_run_id> \
  --run candidate=outputs/roi_proposal_validation/<candidate_run_id> \
  --preset disagreement \
  --max-frames 80 \
  --output-root outputs/roi_proposal_validation/<comparison_id>
```

Frame preset:

- `disagreement`: run 간 GT containment 결과가 다른 frame
- `missed`: 하나 이상의 run이 GT를 놓친 frame
- `cost`: ROI 면적 또는 fallback 차이가 큰 frame
- `--frame <id>`: 명시한 frame만 비교

출력:

```text
<comparison_root>/
  frames/
  manifest.json
  summary.md
  summary.json
```

Run manifest의 dataset segment 또는 target class가 다르면 비교를 중단한다.

## E2E Visualization

Full-frame YOLO와 ROI YOLO detection 비교는 별도 E2E pipeline의 `visualization/renderer.py`를 사용한다. ROI proposal debug/review/compare workflow와 혼합하지 않는다.
