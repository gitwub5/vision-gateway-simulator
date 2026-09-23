# Experiment Entry Points

`experiments/`에는 pipeline을 실행하는 CLI entrypoint와 완료된 연구 실험의 재현 script가 있습니다.

처음 사용하는 경우 root의 대표 runner만 확인하면 됩니다. Phase별 하위 폴더는 과거 결과를 재현하거나 해당 접근을 다시 검토할 때 사용합니다.

## 어떤 파일을 사용해야 하는가

| 목적 | 실행 파일 |
|---|---|
| dataset frame을 정상적으로 읽는지 확인 | `inspect_dataset_stream.py` |
| ROI generator만 빠르게 실행 | `run_rule_roi_baseline.py` |
| ROI proposal을 ground truth와 평가 | `run_roi_proposal_validation.py` |
| ROI gate와 YOLO를 end-to-end로 평가 | `run_e2e_inference_validation.py` |
| 여러 ROI profile을 동일 dataset에서 비교 | `run_validation_matrix.py` |

새로운 일반 목적 validation은 위 runner를 우선 사용합니다.

## 구조

```text
experiments/
  README.md
  inspect_dataset_stream.py
  run_rule_roi_baseline.py
  run_roi_proposal_validation.py
  run_e2e_inference_validation.py
  run_validation_matrix.py
  runner_common.py
  validation_common.py
  phase1_legacy/
  phase1_3/
```

### Root runner

현재 pipeline을 확인할 때 사용하는 기준 entrypoint입니다.

- `runner_common.py`: run id, manifest, config/Git provenance helper
- `validation_common.py`: ROI metadata validation 공통 실행 helper

두 helper는 직접 실행하지 않습니다.

### `phase1_legacy/`

Phase 1에서 pipeline 단계를 개별 실행하기 위해 사용했던 entrypoint입니다.

```text
run_full_frame_baseline.py
run_roi_yolo_inference.py
compare_results.py
render_visualizations.py
```

현재는 보통 `run_e2e_inference_validation.py` 하나로 같은 흐름을 실행합니다. 저장된 중간 artifact를 단계별로 다시 처리하거나 Phase 1 기록을 재현할 때만 legacy script를 사용합니다.

### `phase1_3/`

Phase 1.3의 architecture 탐색 결과를 재현하는 연구용 script입니다.

| 실험군 | 파일 |
|---|---|
| Temporal gate | `run_temporal_gate_poc.py`, `run_temporal_gate_matrix.py` |
| Static zone prior | `run_static_zone_prior_poc.py`, `run_static_zone_prior_matrix.py` |
| Tracker memory | `run_tracker_memory_poc.py`, `run_tracker_memory_matrix.py` |
| Lightweight visual signal | `run_lightweight_visual_signal_poc.py`, `run_lightweight_visual_signal_matrix.py` |
| Compression signal | `run_compression_signal_poc.py`, `run_compression_signal_matrix.py` |
| Traffic prior | `run_velocity_prior_tracker_poc.py`, `run_road_region_prior_poc.py` |
| Hybrid validation | `run_static_tracker_temporal_hybrid_poc.py`, `run_static_lightweight_hybrid_poc.py` |
| Candidate selection/review | `run_hybrid_gate_candidate_selection.py`, `render_phase1_3_visualizations.py` |

이 파일들은 일반 사용자가 모두 실행해야 하는 pipeline이 아닙니다. 관련 결과 문서는 `docs/runs/phase1_3/`에 있으며, 현재 결론은 `docs/current_status.md`를 우선합니다.

## 실행 규칙

- 모든 script는 repository root에서 실행합니다.
- 하위 폴더 script도 module 실행이 아니라 파일 경로 실행을 기준으로 문서화합니다.
- 새 일반 목적 runner는 root에 추가합니다.
- 특정 Phase 결과를 재현하는 script는 해당 Phase 폴더에 둡니다.
- 공통 계산 로직은 experiment script에 복제하지 않고 `roi_generator/`, `evaluation/`, `visualization/`의 적절한 모듈에 둡니다.
- 실행 결과는 `outputs/`에 저장하고 Git에 commit하지 않습니다.

예시:

```bash
python experiments/run_roi_proposal_validation.py --help
python experiments/phase1_3/run_temporal_gate_poc.py --help
python experiments/phase1_legacy/run_full_frame_baseline.py --help
```
