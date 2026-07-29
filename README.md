# Vision Frontend Simulator

Vision Frontend Simulator는 카메라와 GPU 사이에 위치할 Vision Frontend Gate 또는 NPX Gate의 효과를 소프트웨어로 먼저 검증하기 위한 사내 시뮬레이션 프로젝트입니다.

목표는 실제 하드웨어, 보드, 칩 구현 전에 **ROI 기반 전처리 게이트가 객체 탐지 성능을 유지하면서 GPU inference workload를 줄일 수 있는지** 확인하는 것입니다.

초기 검증에서는 실제 NPX 하드웨어나 SNN 모델을 사용하지 않고, OpenCV 기반 rule-based 영상처리로 ROI Gate를 에뮬레이션합니다.

## 현재 범위

현재 우선순위는 **Phase 1. Rule-based ROI Gate 검증**입니다.

Phase 1에서는 다음 흐름을 비교합니다.

```text
A. Full-frame YOLOv8
B. Rule-based ROI Gate + ROI YOLOv8
C. Rule-based ROI Gate + ROI YOLOv8 + Periodic Full-frame Check
```

Phase 1의 구현 현황, 체크리스트, R&R은 [docs/plan/phase1_implementation_plan.md](docs/plan/phase1_implementation_plan.md)를 기준으로 관리합니다.

작업할 때는 다음 원칙을 지킵니다.

- Task 진행 상태를 바꾸면 `docs/plan/phase1_implementation_plan.md`를 함께 수정합니다.
- Task 구현이 끝나면 `docs/tasks/phase*/` 아래에 구현 설명 문서를 남깁니다.
- Phase별 상세 검증 계획이나 다음 Phase 계획은 `docs/plan/` 아래에 정리합니다.
- 개인적인 기술 고민이나 공유 전 의사결정 메모는 Git에 올리지 않는 `docs/idea/` 아래에 둡니다.
- 대용량 dataset, model weight, 실험 output은 Git에 포함하지 않습니다.

## 빠른 실행

가상환경을 권장합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Synthetic fixed-camera smoke video 생성:

```bash
python tools/create_smoke_video.py
```

Rule-based ROI Gate smoke 실행:

```bash
python experiments/run_rule_roi_baseline.py \
  --dataset-config configs/dataset.smoke.yaml \
  --gate-config configs/npx_gate.smoke.yaml \
  --limit 60
```

전체 Phase 1 실험 실행:

```bash
python experiments/run_phase1_experiment.py \
  --dataset-config configs/dataset.opencv_vtest.yaml \
  --gate-config configs/npx_gate.yaml \
  --yolo-config configs/yolo.yaml \
  --experiment-name opencv_vtest \
  --limit 120
```

실험 결과는 `outputs/experiments/<timestamp>_<experiment_name>/` 아래에 묶어서 저장됩니다.
Oxford Town Centre를 실행할 때는 `--gate-config configs/npx_gate.oxford.yaml`을 사용합니다.

테스트:

```bash
python -m unittest discover -s tests
```

## 폴더 구조

| 경로 | 용도 |
|---|---|
| `README.md` | 프로젝트 목적, 실행 방법, 폴더 역할을 안내하는 첫 문서 |
| `.agents/` | Codex 또는 자동화 agent가 먼저 읽을 작업 기준 |
| `docs/plan/` | 공유 가능한 Phase별 구현 계획, 검증 계획, 다음 단계 계획 |
| `docs/tasks/phase*/` | Phase별 Task 구현 설명 문서 |
| `docs/idea/` | 개인 기술 고민, 전략 메모, 의사결정 초안. Git 제외 |
| `docs/assets/` | 문서에서 사용하는 대표 이미지와 시각화 예시 |
| `configs/` | dataset, gate, YOLO 실험 설정 |
| `common/` | loader, gate, inference, evaluation이 공유하는 schema |
| `data_loader/` | video/image sequence 입력을 `FramePacket`으로 변환 |
| `npx_emulator/` | rule-based ROI Gate emulator |
| `gpu_inference/` | full-frame YOLO, ROI YOLO, 좌표 복원 |
| `evaluation/` | recall, ROI containment, workload, latency 비교 |
| `visualization/` | ROI overlay, detection comparison, failure case 렌더링 |
| `experiments/` | 각 모듈을 연결해서 산출물을 생성하는 실행 스크립트 |
| `tools/` | sample data 다운로드, smoke video 생성 등 보조 도구 |
| `tests/` | 단위 테스트 |
| `outputs/` | 실험 결과 저장 위치. 실행 단위 결과는 `outputs/experiments/` 아래에 저장 |
| `data/` | dataset 저장 위치. Git 제외 |

## 주요 문서

| 문서 | 용도 |
|---|---|
| [docs/plan/phase1_implementation_plan.md](docs/plan/phase1_implementation_plan.md) | Phase 1 구현 체크리스트, R&R, 다음 작업 |
| [docs/plan/phase1_validation_plan.md](docs/plan/phase1_validation_plan.md) | Phase 1 공유용 검증 실행 절차와 산출물 규칙 |
| [docs/plan/vision_frontend_validation_roadmap.md](docs/plan/vision_frontend_validation_roadmap.md) | Phase 2 이후 장기 로드맵 |
| [docs/README.md](docs/README.md) | 문서 디렉터리 운영 규칙 |
| [docs/sample_data.md](docs/sample_data.md) | 공개 sample data 준비 방법 |
| [docs/smoke_test.md](docs/smoke_test.md) | synthetic fixed-camera smoke test 사용법 |
| [docs/smoke_test_visualization_result.md](docs/smoke_test_visualization_result.md) | smoke visualization 실행 결과 |

## 협업 메모

- `common/schemas.py` 변경은 전체 pipeline에 영향을 주므로 사전에 공유합니다.
- `configs/*.yaml` 변경은 실험 결과에 영향을 주므로 report 또는 plan 문서에 이유를 남깁니다.
- ROI metadata schema는 inference, evaluation, visualization이 공유하는 계약으로 취급합니다.
- Phase 1에서는 SNN, 실제 NPX 하드웨어, RTSP, DeepStream, TensorRT를 직접 구현하지 않습니다.
