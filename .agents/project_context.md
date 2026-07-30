# Agent Project Context

이 파일은 Codex 또는 자동화 agent가 이 프로젝트를 빠르게 파악하기 위한 첫 진입점이다.

## 프로젝트 한 줄 요약

`vision-frontend-simulator`는 카메라와 GPU 사이의 Vision Frontend / NPX Gate 아이디어를 소프트웨어로 검증하는 Python 프로젝트다.

현재 공유 구현 범위는 **Phase 1. Rule-based ROI Gate pipeline**이다.

```text
Dataset stream
  -> rule-based ROI gate
  -> ROI metadata
  -> full-frame / ROI YOLO inference
  -> evaluation report
  -> visualization
```

## 먼저 읽을 문서

1. `README.md`
   - 프로젝트 목적, 빠른 실행, 폴더 역할을 확인한다.

2. `docs/README.md`
   - 공유 문서와 로컬 idea 문서의 경계를 확인한다.

3. `docs/plan/phase1_implementation_plan.md`
   - Phase 1 구현 체크리스트, R&R, 구현 순서, 파일 구조를 확인한다.

4. `docs/tasks/README.md`
   - Task 문서가 Phase별로 정리되는 규칙을 확인한다.

5. 필요한 Task 문서
   - Phase 1 구현 세부 내용은 `docs/tasks/phase1/` 아래에 있다.

## 문서 구조

```text
docs/
  README.md
  plan/
    README.md
    phase1_implementation_plan.md
    phase1_validation_plan.md
    vision_frontend_validation_roadmap.md
  tasks/
    README.md
    phase1/
      task2_dataset_stream_loader.md
      task3_rule_based_roi_gate.md
      task4_roi_metadata.md
      task5_full_frame_yolo_baseline.md
      task6_roi_yolo_inference.md
      task7_evaluation.md
      task8_visualization.md
  runs/
    phase1_validation_runs.md
  idea/       # gitignored, local-only
```

## 중요 문서 경계

- `docs/plan/`에는 공유 가능한 구현 계획, 실행 절차, 산출물 위치만 둔다.
- `docs/tasks/phase*/`에는 실제 구현 과정과 사용법을 둔다.
- `docs/runs/`에는 공유 가능한 검증 실행 기록과 report 위치를 둔다.
- `docs/idea/`에는 검증 가설, 성공 기준 초안, ROI 개선 고민, SNN 전환 판단, DeepStream 포지셔닝 같은 비공개 기술 메모를 둔다.
- `docs/idea/`는 `.gitignore` 대상이다. 사용자가 명시적으로 요청하지 않는 한 이 내용을 공유 문서로 옮기지 않는다.

## 현재 상태

- Phase 1 Task 1~8 구현 문서는 작성되어 있다.
- 공유 validation 문서는 상세 판단 기준이 아니라 실행 절차와 산출물 규칙만 남긴 상태다.
- Phase 1.1 후보 고민은 ROI crop/gate policy 개선이다.
- Phase 2 SNN 전환, DeepStream과의 경계, 사업성 판단은 `docs/idea/`에서 로컬 메모로 관리한다.

## 주요 코드 위치

| 경로 | 역할 |
|---|---|
| `common/` | 공유 schema |
| `data_loader/` | video/image sequence loader |
| `npx_emulator/` | rule-based ROI gate, event map, ROI metadata |
| `gpu_inference/` | full-frame YOLO, ROI YOLO, coordinate restore |
| `evaluation/` | recall, containment, workload, latency report |
| `visualization/` | ROI overlay, comparison, failure case render |
| `experiments/` | end-to-end 실행 script |
| `configs/` | dataset/gate/YOLO config |
| `tools/` | sample data, smoke video, auxiliary scripts |

## 빠른 검증 명령

이 환경에서는 `python` 대신 `python3`를 우선 사용한다.

```bash
python3 -m unittest discover -s tests
```

전체 Phase 1 실험 예시는 `README.md`와 `docs/plan/phase1_validation_plan.md`를 따른다.

## 작업 원칙

- 사용자 변경을 되돌리지 않는다.
- 실험 결과에 영향을 주는 threshold, ROI policy, model config 변경은 config 또는 문서에 이유를 남긴다.
- ROI metadata schema는 inference, evaluation, visualization이 공유하는 계약으로 취급한다.
- 대용량 dataset, model weight, 실험 output은 Git에 포함하지 않는다.
- 전략성 판단은 먼저 `docs/idea/`에 둔다. 공유 가능한 결론으로 정리된 경우에만 `docs/plan/`으로 승격한다.
- DeepStream과 겹치는 단순 ROI crop/inference 재구현보다, dynamic ROI proposal, policy controller, tracking-assisted ROI, batching/fallback decision 같은 차별화 지점을 우선 검토한다.
