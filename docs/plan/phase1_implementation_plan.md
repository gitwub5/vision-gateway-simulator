# Vision Frontend Simulator Phase 1 구현 관리

## 1. 문서 목적

이 문서는 Phase 1 구현 작업의 범위, R&R, 체크리스트, 파일 구조를 관리한다.

검증 가설, 성공 기준, ROI 개선 방향, SNN 전환 판단, DeepStream 포지셔닝 같은 기술적 고민은 Git에 올리지 않는 `docs/idea/`에서 먼저 정리한다.

## 2. 현재 구현 우선순위

현재 우선순위는 `Phase 1. Rule-based ROI generator 검증`이다.

Phase 1에서는 다음을 구현한다.

- Dataset video 또는 image sequence loader
- Full-frame YOLOv8 baseline
- Rule-based ROI generator emulator
- ROI crop 생성
- ROI crop 기반 YOLOv8 inference
- detection 좌표 복원
- workload, recall, ROI 품질 비교 리포트
- ROI 및 detection 시각화

## 3. 협업 R&R

두 명이 동시에 작업할 때는 파일 충돌을 줄이기 위해 역할을 다음처럼 나눈다. 이름이 정해지기 전까지는 `Owner A`, `Owner B`로 표기한다.

### 역할 구분

| 역할 | 담당 영역 | 주요 책임 |
|---|---|---|
| Owner A | 데이터 입력 + ROI generator pipeline | dataset loader, frame schema 사용, rule-based ROI 생성, ROI metadata 생성 |
| Owner B | GPU inference + evaluation pipeline | YOLO baseline, ROI YOLO, 좌표 복원, metric 계산, report/visualization |
| Shared | 공통 계약 + 실험 설정 | `common/schemas.py`, `configs/**/*.yaml`, `docs/plan/phase1_implementation_plan.md`, README, 문서 |

### 파일 Ownership

| 경로 | Primary Owner | Secondary Reviewer | 비고 |
|---|---|---|---|
| `data_loader/` | Owner A | Owner B | Dataset stream, annotation loader |
| `roi_generator/` | Owner A | Owner B | Rule-based gate, event map, ROI 생성 |
| `gpu_inference/` | Owner B | Owner A | YOLO full-frame, ROI YOLO, coordinate restore |
| `evaluation/` | Owner B | Owner A | recall, containment, workload, latency metric |
| `experiments/` | Owner B | Owner A | 실행 script, comparison report orchestration |
| `common/` | Shared | Shared | schema 변경 전 상호 확인 필요 |
| `configs/` | Shared | Shared | 실험 재현성에 영향, 변경 시 plan/report에 기록 |
| `outputs/` | Shared | Shared | 산출물 위치만 공유, 대용량 결과는 Git 제외 |
| `README.md` | Shared | Shared | 외부/팀원 안내 문서 |
| `docs/plan/phase1_implementation_plan.md` | Shared | Shared | Phase 1 체크리스트와 R&R 관리 문서 |
| `docs/plan/` | Shared | Shared | Phase별 상세 계획과 다음 Phase 계획 |
| `docs/` | Shared | Shared | 상세 설계/로드맵 문서 |

### 작업 충돌 방지 규칙

- 각자 Primary Owner인 디렉터리를 우선 수정한다.
- `common/schemas.py` 변경은 두 사람 모두에게 영향을 주므로, 변경 전에 필요한 필드와 호환성을 먼저 합의한다.
- `configs/**/*.yaml` 변경은 실험 결과에 영향을 주므로, 변경 이유와 기본값을 `docs/plan/phase1_implementation_plan.md` 또는 report에 남긴다.
- 한 Task가 여러 ownership을 건드리면 PR 또는 커밋 설명에 변경 범위를 명확히 적는다.
- 같은 파일을 동시에 수정해야 하면 먼저 작은 interface 변경 커밋을 만든 뒤 각자 구현을 이어간다.
- 체크박스는 해당 Task의 Primary Owner가 갱신하고, Secondary Reviewer가 결과를 확인한다.
- 모든 Task 구현자는 작업 완료 시 `docs/tasks/phase*/` 아래에 구현 설명 문서를 작성한다.

### Task 완료 문서화 규칙

모든 Task는 코드 구현, 테스트/검증, 구현 설명 문서 작성이 모두 끝났을 때만 완료 처리한다.

문서 파일명은 다음 형식을 따른다.

```text
docs/tasks/phase{Phase번호}/task{번호}_{짧은_설명}.md
```

예:

```text
docs/tasks/phase1/task2_dataset_stream_loader.md
docs/tasks/phase1/task3_rule_based_roi_generator.md
```

각 Task 문서에는 최소한 다음 내용을 포함한다.

- 구현 목적
- 변경한 주요 파일
- 핵심 설계 결정과 이유
- 실행 방법 또는 사용 예시
- 검증 방법
- 다음 Task와의 연결
- 알려진 제한사항 또는 후속 작업

### Phase 1 Task 담당

| Task | Primary Owner | Secondary Reviewer | 주요 파일 |
|---|---|---|---|
| Task 1. 프로젝트 스캐폴딩 | Shared | Shared | `common/`, `configs/`, skeleton 전체 |
| Task 2. Dataset Stream Loader | Owner A | Owner B | `data_loader/`, `common/schemas.py`, `configs/datasets/default.yaml` |
| Task 3. Rule-based ROI generator Emulator | Owner A | Owner B | `roi_generator/`, `configs/roi_generator/default.yaml` |
| Task 4. ROI Metadata 저장 | Owner A | Owner B | `roi_generator/metadata.py`, `common/schemas.py`, `outputs/roi_metadata/` |
| Task 5. Full-frame YOLO Baseline | Owner B | Owner A | `gpu_inference/yolo_full_frame.py`, `experiments/run_full_frame_baseline.py`, `configs/models/yolo_default.yaml` |
| Task 6. ROI YOLO Inference | Owner B | Owner A | `gpu_inference/yolo_roi.py`, `gpu_inference/coordinate_restore.py` |
| Task 7. Evaluation | Owner B | Owner A | `evaluation/`, `experiments/compare_results.py`, `outputs/reports/` |
| Task 8. Visualization | Owner B | Owner A | `outputs/visualizations/`, visualization helper modules |
| Support. Sample Data Utility | Owner A | Owner B | `tools/download_sample_data.py`, `docs/sample_data.md`, `configs/datasets/*.yaml` |

## 4. 구현 체크리스트

체크박스는 실제 구현, 최소 동작 확인, `docs/tasks/phase*/` 구현 설명 문서 작성이 모두 끝났을 때 갱신한다. 단순 파일 생성만으로 완료 처리하지 않고, 해당 단계의 산출물이 생성되거나 다음 단계에서 사용할 수 있는 인터페이스가 준비되었을 때 완료로 본다.

### Phase 1. Rule-based ROI generator 검증

- [x] Task 1. 프로젝트 스캐폴딩
  - [x] 기본 디렉터리 생성
  - [x] config 파일 기본값 작성
  - [x] 공통 schema 정의
  - [x] 실행 스크립트 입출력 경로 통일
- [x] Task 2. Dataset Stream Loader
  - [x] video loader 구현
  - [x] image sequence loader 구현
  - [x] `FramePacket` 생성
  - [x] annotation loader 확장 지점 준비
- [x] Task 3. Rule-based ROI generator Emulator
  - [x] gray 변환 및 resize
  - [x] frame difference
  - [x] ON/OFF event-like map 생성
  - [x] threshold 기반 motion map
  - [x] morphology 및 small component filtering
  - [x] connected component 기반 ROI 후보 생성
  - [x] ROI merge
  - [x] ROI margin 및 원본 좌표 변환
  - [x] temporal hold
  - [x] periodic full-frame trigger
  - [x] ROI 과다/대면적 full-frame fallback
- [x] Task 4. ROI Metadata 저장
  - [x] ROI metadata schema 확정
  - [x] JSONL writer 구현
  - [x] frame별 trigger type 기록
  - [x] crop inference/evaluation에서 재사용 가능한 형식 확인
- [x] Task 5. Full-frame YOLO Baseline
  - [x] YOLOv8n full-frame inference 구현
  - [x] detection JSONL 저장
  - [x] latency 측정
  - [x] workload metric 기록
- [x] Task 6. ROI YOLO Inference
  - [x] ROI crop 생성
  - [x] crop YOLO inference 구현
  - [x] crop detection 좌표 원본 좌표로 복원
  - [x] periodic full-frame check 결과 병합
- [x] Task 7. Evaluation
  - [x] recall 유지율 계산
  - [x] ROI containment rate 계산
  - [x] YOLO 호출 수 감소율 계산
  - [x] YOLO 입력 픽셀 면적 감소율 계산
  - [x] 평균 ROI 수와 평균 ROI 면적 계산
  - [x] gate latency 계산
  - [x] comparison report 생성
- [x] Task 8. Visualization
  - [x] ROI overlay 이미지 생성
  - [x] full-frame detection과 ROI-gated detection 비교 시각화
  - [x] 실패 사례 저장

### Phase 2 이후

- [ ] Phase 2. SNN Tile Eventness Model 검증
- [ ] Phase 3. Multi-camera Simulation
- [ ] Phase 4. GPU Pipeline Optimization
- [ ] Phase 5. Hardware-oriented Spec 도출
- [ ] Phase 6. 실제 Edge Pipeline PoC
- [ ] Phase 7. 사업화 기준 검증

### Support Tasks

- [x] Synthetic fixed-camera smoke video 생성 도구
- [x] 공개 sample dataset download script
- [x] dataset별 usage note 정리
- [x] `data/` 저장 경로 표준화
- [x] smoke test 실행 안내 출력

## 5. Phase 1 구현 범위 메모

Phase 1 구현은 full-frame baseline, rule-based ROI generator, ROI YOLO inference, evaluation, visualization을 연결하는 데 집중한다.

비공개 검증 기준과 다음 단계 판단 메모는 `docs/idea/`에서 관리한다.

## 6. 구현 순서

### [x] Task 1. 프로젝트 스캐폴딩

목표:

- 디렉터리 구조 생성
- config 기본값 작성
- 공통 데이터 구조 정의
- 실행 스크립트의 입출력 경로 통일

예상 산출물:

```text
configs/
├── datasets/
├── roi_generator/
└── models/
data_loader/
roi_generator/
gpu_inference/
evaluation/
experiments/
outputs/
```

### [x] Task 2. Dataset Stream Loader

목표:

- OpenCV 기반 video loader 구현
- image sequence loader 구현
- `frame_id`, `timestamp`, `camera_id`, `frame`을 포함한 frame packet 생성
- 추후 annotation loader를 붙일 수 있는 구조 유지

초기 입력 데이터 준비 방법은 `docs/sample_data.md`를 따른다.

### [x] Task 3. Rule-based ROI generator Emulator

목표:

- gray 변환
- low-resolution analysis frame 생성
- frame difference
- ON/OFF event-like map 생성 코드 분리
- threshold 기반 motion map 생성
- morphology 기반 noise filtering
- connected component 기반 ROI 후보 생성
- ROI merge
- ROI margin 추가
- 원본 좌표계 변환
- temporal hold
- periodic full-frame trigger

구현상 유지할 계약:

- Phase 1에서는 `motion_map`만 사용해도 되지만, Phase 2 SNN 확장을 위해 `on_event`, `off_event`, `motion_map` 생성 코드는 분리한다.
- ROI가 너무 많거나 전체 면적이 너무 크면 full-frame fallback이 가능해야 한다.

### [x] Task 4. ROI Metadata 저장

목표:

- frame별 ROI 결과를 JSONL로 저장
- crop inference와 평가 코드가 동일한 metadata를 사용하도록 한다.

예상 출력:

```text
outputs/roi_metadata/rule_roi.jsonl
outputs/roi_metadata/gate_decisions.jsonl
```

권장 metadata 필드:

```json
{
  "camera_id": "cam_01",
  "frame_id": 1024,
  "timestamp": 1780000000.123,
  "roi_id": "cam_01_f1024_roi_01",
  "original_frame_size": [1920, 1080],
  "analysis_frame_size": [256, 144],
  "roi_xywh": [640, 320, 420, 560],
  "score": 0.82,
  "source": "rule_based_roi_generator",
  "trigger_type": "roi"
}
```

### [x] Task 5. Full-frame YOLO Baseline

목표:

- YOLOv8n으로 전체 프레임 inference 수행
- frame별 detection 결과 저장
- inference latency 측정
- YOLO 호출 수와 입력 픽셀 면적 기록

예상 출력:

```text
outputs/detections/full_frame.jsonl
outputs/reports/full_frame_metrics.json
```

초기 구현은 full-frame YOLO 결과를 비교 기준으로 사용할 수 있게 저장한다.

### [x] Task 6. ROI YOLO Inference

목표:

- ROI metadata 기준으로 원본 frame에서 crop 생성
- ROI crop을 YOLOv8에 입력
- crop 좌표계 detection을 원본 좌표계로 복원
- periodic full-frame check 결과와 병합 가능하게 설계

예상 출력:

```text
outputs/detections/roi_yolo.jsonl
outputs/reports/roi_yolo_metrics.json
```

### [x] Task 7. Evaluation

목표:

- Full-frame baseline과 ROI-gated 결과 비교
- recall 유지율 계산
- ROI containment rate 계산
- YOLO 호출 수 감소율 계산
- YOLO 입력 픽셀 면적 감소율 계산
- 평균 ROI 개수와 평균 ROI 면적 계산
- Gate latency 측정

예상 출력:

```text
outputs/reports/comparison_report.json
outputs/reports/comparison_report.md
```

### [x] Task 8. Visualization

목표:

- 원본 frame 위에 ROI box 표시
- full-frame detection과 ROI-gated detection 비교
- 실패 사례를 이미지 또는 영상으로 저장

예상 출력:

```text
outputs/visualizations/
```

## 7. 권장 프로젝트 구조

```text
vision-frontend-simulator/
├── README.md
├── requirements.txt
├── docs/
│   ├── plan/
│   │   ├── phase1_implementation_plan.md
│   │   ├── phase1_validation_plan.md
│   │   └── vision_frontend_validation_roadmap.md
│   ├── sample_data.md
│   ├── smoke_test.md
│   ├── idea/                 # local only, gitignored
│   └── tasks/
│       └── phase1/
│           ├── task2_dataset_stream_loader.md
│           ├── task3_rule_based_roi_generator.md
│           ├── task4_roi_metadata.md
│           ├── task5_full_frame_yolo_baseline.md
│           ├── task6_roi_yolo_inference.md
│           ├── task7_evaluation.md
│           └── task8_visualization.md
├── .agents/
│   └── project_context.md
├── configs/
│   ├── datasets/
│   │   ├── default.yaml
│   │   └── smoke.yaml
│   ├── roi_generator/
│   │   ├── default.yaml
│   │   └── smoke.yaml
│   └── models/
│       └── yolo_default.yaml
├── common/
│   └── schemas.py
├── data_loader/
│   ├── dataset_stream.py
│   └── annotation_loader.py
├── roi_generator/
│   ├── preprocess.py
│   ├── event_encoder.py
│   ├── motion_detector.py
│   ├── roi_generator.py
│   ├── gate.py
│   ├── temporal_hold.py
│   └── metadata.py
├── gpu_inference/
│   ├── yolo_full_frame.py
│   ├── yolo_roi.py
│   └── coordinate_restore.py
├── evaluation/
│   ├── comparison_report.py
│   ├── detection_metrics.py
│   ├── roi_containment.py
│   ├── workload_metrics.py
│   └── latency_metrics.py
├── visualization/
│   └── renderer.py
├── experiments/
│   ├── run_full_frame_baseline.py
│   ├── run_roi_yolo_inference.py
│   ├── run_rule_roi_baseline.py
│   ├── inspect_dataset_stream.py
│   ├── render_visualizations.py
│   └── compare_results.py
├── tests/
│   ├── test_dataset_stream.py
│   ├── test_roi_generator.py
│   ├── test_roi_metadata.py
│   ├── test_yolo_full_frame.py
│   ├── test_yolo_roi.py
│   ├── test_evaluation.py
│   └── test_visualization.py
├── tools/
│   ├── download_sample_data.py
│   └── create_smoke_video.py
└── outputs/
    ├── detections/
    ├── roi_metadata/
    ├── visualizations/
    └── reports/
```

## 8. 초기 Config 기준

### Dataset

```yaml
dataset:
  type: video
  input_path: data/sample.mp4
  camera_id: cam_01
  fps_override: null
  frame_limit: null
```

### ROI Generator

```yaml
roi_generator:
  analysis_width: 256
  analysis_height: 144
  threshold_motion: 25
  threshold_on: 15
  threshold_off: 15
  morphology_kernel_size: 3
  min_area_ratio: 0.001
  merge_distance_ratio: 0.08
  margin_ratio: 0.25
  hold_frames: 15
  full_frame_interval: 60
  max_roi_per_frame: 5
  max_total_roi_area_ratio: 0.5
```

### YOLO

```yaml
yolo:
  model: yolov8n.pt
  image_size: 640
  confidence_threshold: 0.25
  iou_threshold: 0.45
  classes:
    - person
    - car
    - truck
    - bus
```

## 9. 검증 판단 메모 위치

Phase 1 성공 기준, 다음 단계 진입 조건, ROI crop 개선 여부, SNN 전환 여부, DeepStream 대비 포지셔닝은 `docs/idea/`에서 로컬 메모로 관리한다.

팀에 공유할 정도로 정리된 결론만 `docs/plan/` 문서로 승격한다.

## 10. 협업 규칙 초안

- 구현은 Phase와 Task 단위로 진행한다.
- 각 Task는 위 R&R 표의 Primary Owner가 주도하고 Secondary Reviewer가 확인한다.
- Phase 1에서는 하드웨어, SNN, RTSP, DeepStream, TensorRT를 직접 구현하지 않는다.
- 실험 결과는 `outputs/` 아래에 저장하되, 대용량 결과물은 Git에 포함하지 않는다.
- config 값이 실험 결과에 영향을 주므로 report에는 사용한 config snapshot을 함께 남긴다.
- metric 계산 방식이 바뀌면 기존 report와 비교 가능하도록 변경 내용을 문서화한다.
- ROI metadata schema는 GPU inference, evaluation, visualization이 공유하는 계약으로 취급한다.

## 11. 문서 역할

- `README.md`: 프로젝트 소개, 빠른 시작, 협업자가 봐야 할 요약
- `docs/plan/phase1_implementation_plan.md`: Phase 1 구현 순서, 체크리스트, R&R
- `docs/plan/phase1_validation_plan.md`: Phase 1 세부 검증 계획
- `docs/plan/`: 다음 Phase 계획과 세부 검증 문서를 정리하는 위치
- `docs/tasks/phase*/`: Phase별 Task 구현 설명 문서
- `docs/idea/`: 개인 기술 고민과 공유 전 의사결정 초안. Git 제외
- `docs/sample_data.md`: 공개 sample data 다운로드와 수동 준비 안내
- `docs/smoke_test.md`: 고정 카메라 synthetic smoke test 생성 및 실행 방법
- `docs/plan/vision_frontend_validation_roadmap.md`: 전체 장기 로드맵
- `.agents/project_context.md`: Codex 또는 자동화 agent가 먼저 확인할 문서 목록과 작업 원칙

## 12. 다음 작업

Phase 1 구현 Task 1~8은 완료된 상태로 관리한다. 다음 작업은 공유 가능한 실행 절차와 산출물 정리다.

```text
1. 가상환경에 전체 의존성 설치
2. fixed-camera sample dataset 준비
3. Task 4~8 end-to-end 실행
4. comparison report와 visualization 결과 위치 기록
5. 공유 가능한 제한사항 또는 버그 정리
6. 전략적 판단 내용은 docs/idea/에서 먼저 정리
```
