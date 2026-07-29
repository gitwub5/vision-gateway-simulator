# Task 4. ROI Metadata 저장 구현 정리

## 목적

Task 4의 목적은 Task 3의 `GateDecision` 결과를 후속 YOLO/evaluation 단계에서 재사용할 수 있는 JSONL 산출물로 저장하는 것이다.

Task 4 이후에는 ROI Gate를 다시 실행하지 않아도 `rule_roi.jsonl`을 읽어서 ROI crop YOLO, workload 계산, visualization을 반복할 수 있다.

## 구현 파일

- `common/schemas.py`
- `npx_emulator/metadata.py`
- `experiments/run_rule_roi_baseline.py`
- `tests/test_roi_metadata.py`

## 산출물

Task 4는 두 종류의 JSONL 파일을 생성한다.

```text
outputs/roi_metadata/rule_roi.jsonl
outputs/roi_metadata/gate_decisions.jsonl
```

### `rule_roi.jsonl`

ROI crop inference를 위한 ROI 단위 작업 목록이다. 한 줄은 하나의 ROI를 의미한다.

```json
{
  "camera_id": "cam_01",
  "frame_id": 42,
  "timestamp": 1.4,
  "roi_id": "cam_01_f000042_roi_001",
  "original_frame_size": [1920, 1080],
  "analysis_frame_size": [256, 144],
  "roi_xywh": [640, 320, 420, 560],
  "score": 0.82,
  "source": "rule_based_roi_gate",
  "trigger_type": "roi"
}
```

### `gate_decisions.jsonl`

Frame 단위 gate decision log다. ROI가 없는 frame도 기록되므로 trigger 통계와 gate latency 계산에 사용한다.

```json
{
  "camera_id": "cam_01",
  "frame_id": 42,
  "timestamp": 1.4,
  "trigger_type": "full_frame",
  "roi_count": 0,
  "should_run_full_frame": true,
  "gate_latency_ms": 0.52,
  "original_frame_size": [1920, 1080],
  "analysis_frame_size": [256, 144],
  "source": "rule_based_roi_gate"
}
```

## 핵심 설계 결정

### ROI metadata와 frame decision log 분리

`rule_roi.jsonl`은 Task 6 ROI YOLO가 읽을 crop 작업 목록이다. 여기에 ROI가 없는 `FULL_FRAME` 또는 `NONE` frame을 넣으면 crop 단계에서 혼란이 생긴다.

그래서 ROI 단위 metadata는 `rule_roi.jsonl`에 저장하고, frame별 trigger와 latency는 `gate_decisions.jsonl`에 따로 저장한다.

```text
rule_roi.jsonl        -> ROI YOLO / ROI area metric / visualization
gate_decisions.jsonl  -> trigger 통계 / gate latency / full-frame check 분석
```

### ROI ID 규칙

ROI ID는 camera, frame, ROI index를 포함한다.

```text
cam_01_f000042_roi_001
```

이 규칙을 쓰는 이유는 ROI crop 결과와 YOLO detection 결과를 안정적으로 다시 연결하기 위해서다.

### JSONL 사용

영상 실험은 frame 단위로 결과가 계속 쌓인다. JSONL은 한 줄씩 append할 수 있어서 긴 영상이나 중간 실패가 있는 실험에 적합하다.

## 실행 방법

```bash
python experiments/run_rule_roi_baseline.py \
  --dataset-config configs/dataset.yaml \
  --gate-config configs/npx_gate.yaml \
  --roi-output outputs/roi_metadata/rule_roi.jsonl \
  --frame-output outputs/roi_metadata/gate_decisions.jsonl
```

일부 frame만 빠르게 확인하려면 `--limit`을 사용한다.

```bash
python experiments/run_rule_roi_baseline.py --limit 100
```

## 검증 방법

```bash
python3 -m compileall common data_loader npx_emulator experiments tests
python3 -m unittest tests.test_dataset_stream tests.test_npx_gate tests.test_roi_metadata
```

검증 항목:

- `GateDecision`에서 ROI별 `ROIMetadata` 생성
- ROI 없는 decision은 ROI metadata를 만들지 않음
- frame별 `GateFrameMetadata` 생성
- ROI ID 생성 규칙 확인
- JSONL writer가 한 줄에 하나씩 JSON 저장
- `run_rule_roi_baseline.py`가 ROI metadata와 frame decision log를 함께 생성

## 다음 Task와의 연결

Task 5에서는 full-frame YOLO baseline을 구현한다.

Task 6에서는 `rule_roi.jsonl`의 `roi_xywh`를 기준으로 원본 frame에서 crop을 생성하고 ROI YOLO inference를 수행한다.

Task 7에서는 `rule_roi.jsonl`과 `gate_decisions.jsonl`을 함께 사용해 workload reduction, ROI 통계, gate latency를 계산한다.
