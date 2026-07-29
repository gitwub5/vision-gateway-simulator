# Phase 1 Validation Plan

이 문서는 Phase 1 검증 실행 과정에서 팀과 공유해야 하는 절차와 산출물 위치만 관리한다.

검증 가설, 성공 기준, ROI 개선 방향, SNN 전환 판단, DeepStream 포지셔닝 같은 기술적 고민은 Git에 올리지 않는 `docs/idea/`에서 먼저 정리한다. 공유가 필요한 수준으로 정리된 내용만 이 문서나 roadmap으로 옮긴다.

## 공유 대상

- 실행한 dataset config
- 실행한 gate config
- 실행한 YOLO config
- 생성된 report와 visualization 위치
- 재현 가능한 실행 명령
- 공유 가능한 제한사항 또는 버그

## 기본 실행 순서

```bash
python experiments/run_phase1_experiment.py \
  --dataset-config <dataset_config> \
  --gate-config <gate_config> \
  --yolo-config configs/yolo.yaml \
  --experiment-name <experiment_name> \
  --limit <frame_limit>
```

## 산출물 위치

```text
outputs/experiments/<timestamp>_<experiment_name>/
```

실험 결과 파일은 대용량이거나 환경 의존적일 수 있으므로 기본적으로 Git에 포함하지 않는다.

## 기록 규칙

- config 값을 바꾼 실험은 사용한 config snapshot을 결과 디렉터리에 남긴다.
- metric 계산 방식이 바뀌면 구현 문서 또는 Task 문서에 변경 이유를 남긴다.
- 외부 공유 전 단계의 해석, 시장성, DeepStream 대비 포지셔닝 메모는 `docs/idea/`에 둔다.
