# Phase 1.2 Experiment Automation

공식 Phase 1.2 비교 실행은 profile registry와 experiment YAML을 통해 관리한다.

## Configuration

- `configs/roi_generator/profiles.yaml`: profile 경로, 역할, 상태, feedback source
- `configs/experiments/phase1_2_baselines.yaml`: dataset, frame limit, diagnostics, 비교 profile

Diagnostics tier는 다음 의미를 유지한다.

- `minimal`: 빠른 metric sweep
- `tile_trace`: Phase 1.2 기본 실행
- `full`: 특정 실패의 generation debug

저수준 단일-run CLI는 ad-hoc 디버깅을 위해 옵션을 유지하지만, 공식 matrix 실행의 diagnostics는 experiment YAML만 수정한다.

## Matrix Dry Run

실행될 profile과 명령을 확인한다. 모델 추론과 validation은 실행하지 않는다.

```bash
python experiments/run_validation_matrix.py \
  --experiment-config configs/experiments/phase1_2_baselines.yaml \
  --dry-run
```

## Run Baseline Matrix

```bash
python experiments/run_validation_matrix.py \
  --experiment-config configs/experiments/phase1_2_baselines.yaml
```

각 profile은 동일 dataset, limit, diagnostics로 순차 실행된다. `feedback_actual_yolo`는 registry에 기록된 `full_frame_yolo` feedback source를 사용한다.

출력:

```text
outputs/validation_matrices/<experiment>_<timestamp>/
  manifest.json
  summary.json
  summary.md
```

특정 profile만 실행할 때는 `--profile <registry_name>`을 반복해서 사용한다.

## Boundary Miss Taxonomy

`tile_trace` 또는 `full`로 완료된 run에서 실행한다.

```bash
python tools/classify_boundary_misses.py \
  --run-root outputs/roi_proposal_validation/<run_id>
```

출력:

```text
<run_root>/reports/
  boundary_misses.jsonl
  false_rois.jsonl
  boundary_misses.md
```

현재 분류:

- `margin_insufficient`: final ROI의 제한된 margin 확장으로 GT containment를 복구할 수 있음
- `adjacent_tile_not_selected`: GT가 selected tile과 인접한 unselected tile에 걸쳐 있음
- `signal_missing`: GT와 겹치는 selected tile이 없음
- `partial_target_boundary`: ROI가 target GT와 교차하지만 완전히 포함하지 못함
- `empty_frame_noise`: target GT가 없는 frame에서 ROI가 생성됨
- `low_density_noise`: target GT와 겹치지 않고 selected tile density가 낮음
- `off_target_motion`: target GT와 겹치지 않지만 selected tile density가 높음

`feedback_needed` 분류는 현재 포함하지 않으며 Phase 1.2 후속 단계에서 추가한다.

Periodic/fallback full-frame decision의 GT는 ROI boundary miss가 아니므로 taxonomy에서 제외하고 Markdown에 제외 수를 기록한다.
