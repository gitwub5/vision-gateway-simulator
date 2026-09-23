# Architecture

## 전체 흐름

```text
Dataset YAML
    |
    v
data_loader                  FramePacket
    |                            |
    +----------------------------+
                                 v
roi_generator              GateDecision
                                 |
                  +--------------+--------------+
                  |                             |
                  v                             v
           ROI metadata                 full-frame decision
                  |                             |
                  +--------------+--------------+
                                 v
gpu_inference                  Detection
                                 |
                  +--------------+--------------+
                  |                             |
                  v                             v
              evaluation                  visualization
                  |                             |
                  +--------------+--------------+
                                 v
                         outputs/<run_id>/
```

`experiments/`의 script가 위 모듈을 연결하고, config와 Git revision을 포함한 manifest 및 report를 생성합니다.

## 핵심 데이터 계약

| 타입 | 위치 | 역할 |
|---|---|---|
| `FramePacket` | `common/schemas.py` | camera/frame 식별자, timestamp, 원본 frame과 크기 |
| `ROI` | `common/schemas.py` | original frame 좌표계의 ROI rectangle |
| `GateDecision` | `roi_generator/core/contract.py` | frame별 ROI, trigger, fallback, cost와 trace를 전달하는 runtime 계약 |
| `ROIMetadata` | `common/schemas.py` | ROI를 JSONL artifact로 저장하기 위한 record |
| `GateFrameMetadata` | `common/schemas.py` | frame 단위 gate 판단과 workload record |
| `Detection` | `common/schemas.py` | full-frame 또는 ROI inference의 탐지 결과 |
| `GroundTruthAnnotation` | `common/schemas.py` | dataset annotation을 공통 형식으로 표현 |

이 타입들을 변경하면 loader, inference, evaluation, visualization이 함께 영향을 받습니다. 새로운 field는 가능한 한 optional/default field로 추가하고 serialization round-trip test를 함께 수정합니다.

## 모듈 책임

### `data_loader/`

- dataset YAML을 `DatasetConfig`로 읽습니다.
- video 또는 image sequence를 `FramePacket` stream으로 변환합니다.
- dataset별 annotation을 공통 `GroundTruthAnnotation`으로 변환합니다.
- frame id가 zero-based인지, upstream annotation이 one-based인지 loader에서 정규화합니다.

### `roi_generator/`

내부 의존 방향은 다음과 같습니다.

```text
signals/ -> candidates/ -> policies/
                    \       /
                     core/gate.py
                          |
                 core/contract.py
                          |
                   observability/
```

- `signals/`: grayscale, resize, event/motion map 생성
- `candidates/`: connected component와 tile 후보 생성
- `policies/`: 후보를 실제 ROI로 선택
- `core/`: config, budget, fallback, temporal hold, feedback, `GateDecision` 조율
- `observability/`: runtime 판단을 JSONL metadata와 debug trace로 변환

새 policy의 세부 로직은 `core/gate.py`에 직접 추가하기보다 `policies/`와 `candidates/`에 둡니다.

### `gpu_inference/`

- `yolo_full_frame.py`: full-frame baseline inference
- `yolo_roi.py`: ROI crop inference와 periodic/fallback full-frame inference
- `coordinate_restore.py`: crop 좌표를 original frame 좌표로 복원

YOLO model은 실제 실행 시 lazy-load됩니다. Unit test에서는 model-compatible fake object를 주입해 외부 weight 없이 검증합니다.

### `evaluation/`

- `metrics/`: detection, ROI containment, workload, latency 계산
- `reports/`: 실험 종류별 JSON/Markdown report 생성
- `system/`: hardware/environment snapshot 수집

Report는 가능하면 runtime 모듈을 직접 호출하지 않고 저장된 metadata와 detection record를 입력으로 사용합니다.

### `visualization/`

저장된 manifest, ROI metadata, detection, ground truth를 읽어 overlay와 비교 이미지를 만듭니다. Visualization은 실험 결과를 변경하지 않는 소비자 역할만 담당합니다.

### `experiments/`

실행 가능한 orchestration script입니다. 파일 선택 기준과 전체 목록은 [`experiments/README.md`](../experiments/README.md)에 있습니다.

- `run_rule_roi_baseline.py`: ROI metadata만 생성
- `run_roi_proposal_validation.py`: ROI proposal과 ground truth 평가
- `run_e2e_inference_validation.py`: gate와 YOLO를 포함한 E2E 검증
- `run_validation_matrix.py`: dataset/profile matrix 실행
- `phase1_legacy/`: Phase 1의 단계별 실행과 중간 artifact 처리
- `phase1_3/run_*_poc.py`, `phase1_3/run_*_matrix.py`: architecture 후보별 연구용 POC

Phase 1.3 POC script는 모두 장기 유지할 runtime API를 의미하지 않습니다. 현재 runtime contract를 확인할 때는 `roi_generator/`, `gpu_inference/`, root의 validation runner를 우선합니다.

## Config 구조

```text
configs/
  datasets/       입력 경로, frame 범위, annotation 품질, target class
  roi_generator/  ROI policy와 threshold, budget, feedback 설정
  models/         YOLO model과 inference threshold
  experiments/    dataset과 profile을 묶은 matrix 실행 설정
```

대부분의 경로는 repository root 기준 상대 경로입니다. 같은 실험을 비교할 때는 dataset segment, target class, diagnostics level, reference feedback source가 같은지 확인합니다.

## Output 구조

대표 validation run은 아래 구조를 사용합니다.

```text
outputs/<pipeline>/<run_id>/
  manifest.json
  annotations/
  detections/
  roi_metadata/
  reports/
  visualizations/
```

`manifest.json`은 run id, 입력 config, resolved dataset 정보, output 경로, Git revision과 dirty 상태를 기록합니다. 결과를 공유할 때는 report만 복사하지 말고 manifest를 함께 보존합니다.

## 확장 시 권장 경계

- 새 dataset은 `data_loader/`와 `configs/datasets/`에 추가합니다.
- 새 ROI policy는 `roi_generator/policies/`와 관련 config/test에 추가합니다.
- 새로운 관측용 수치는 `GateDecision` 또는 trace에 기록하고 evaluation에서 계산합니다.
- domain별 architecture가 공통으로 필요로 하는 merge/packing과 budget은 experiment script에 복제하지 않고 `roi_generator/core/`의 공통 기능으로 구현합니다.
- hardware/RTSP/DeepStream 연동은 현재 simulator와 별도 adapter/runtime 계층으로 두는 것이 안전합니다.
