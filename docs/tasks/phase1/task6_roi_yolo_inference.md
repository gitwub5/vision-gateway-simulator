# Task 6. ROI YOLO Inference 구현 정리

## 목적

Task 6의 목적은 Task 4에서 저장한 ROI metadata를 기준으로 원본 frame에서 crop을 만들고, crop YOLO inference 결과를 원본 frame 좌표계 detection으로 복원하는 것이다.

```text
DatasetStream + rule_roi.jsonl + gate_decisions.jsonl
    ↓
ROI crop / periodic full-frame check
    ↓
YOLOv8 inference
    ↓
restored Detection JSONL + ROI YOLO metrics
```

## 변경한 주요 파일

- `gpu_inference/yolo_roi.py`
- `gpu_inference/coordinate_restore.py`
- `gpu_inference/__init__.py`
- `gpu_inference/yolo_full_frame.py`
- `experiments/run_roi_yolo_inference.py`
- `tests/test_yolo_roi.py`
- `docs/plan/phase1_implementation_plan.md`
- `README.md`

## 핵심 설계 결정

### `rule_roi.jsonl` reader

Task 4의 `rule_roi.jsonl`은 ROI crop inference를 위한 ROI 단위 작업 목록이다.

Task 6에서는 이 JSONL을 다시 `ROIMetadata`로 읽어 `camera_id + frame_id` 기준으로 frame stream과 매칭한다.

### `gate_decisions.jsonl` 기반 full-frame check 병합

Task 4는 frame별 gate decision을 `gate_decisions.jsonl`에 저장한다.

Task 6에서는 `should_run_full_frame`이 `true`인 frame에 대해 full-frame YOLO를 추가 실행하고, 결과를 ROI YOLO detection과 같은 JSONL에 병합한다.

source 값은 다음처럼 구분한다.

```text
roi_yolo
roi_yolo_full_frame_check
```

### 좌표 복원

ROI crop에서 나온 YOLO bbox는 crop 좌표계다.

`restore_xyxy_from_crop()`을 사용해 ROI offset을 더하고 원본 frame 좌표계로 복원한다.

```text
crop bbox [x1, y1, x2, y2]
    + roi offset [roi.x, roi.y]
    ↓
original-frame bbox
```

### ROI YOLO metric

Task 6 metric은 ROI-gated inference 자체의 workload를 기록한다.

기록 항목:

- `frame_count`
- `roi_record_count`
- `roi_yolo_call_count`
- `full_frame_check_call_count`
- `yolo_call_count`
- `roi_input_pixel_area`
- `full_frame_input_pixel_area`
- `yolo_input_pixel_area`
- frame/crop별 `latency_ms`
- `average_latency_ms`
- `average_roi_count`
- `detection_count`
- 사용한 YOLO config snapshot

Task 7에서는 이 값을 Task 5의 full-frame baseline과 비교해 workload reduction을 계산한다.

## 실행 방법

먼저 ROI metadata를 생성한다.

```bash
python experiments/run_rule_roi_baseline.py \
  --dataset-config configs/dataset.yaml \
  --gate-config configs/npx_gate.yaml \
  --roi-output outputs/roi_metadata/rule_roi.jsonl \
  --frame-output outputs/roi_metadata/gate_decisions.jsonl
```

그 다음 ROI YOLO inference를 실행한다.

```bash
python experiments/run_roi_yolo_inference.py \
  --dataset-config configs/dataset.yaml \
  --yolo-config configs/yolo.yaml \
  --roi-metadata outputs/roi_metadata/rule_roi.jsonl \
  --frame-metadata outputs/roi_metadata/gate_decisions.jsonl
```

짧은 구간만 실행:

```bash
python experiments/run_roi_yolo_inference.py \
  --dataset-config configs/dataset.yaml \
  --yolo-config configs/yolo.yaml \
  --limit 10
```

periodic full-frame check를 제외하고 ROI crop만 실행:

```bash
python experiments/run_roi_yolo_inference.py \
  --disable-full-frame-checks
```

## 검증 방법

```bash
python3 -m compileall common data_loader npx_emulator gpu_inference evaluation experiments tests tools
python3 -m unittest tests.test_yolo_roi
```

검증 항목:

- `rule_roi.jsonl` contract를 `ROIMetadata`로 복원
- `gate_decisions.jsonl` contract를 `GateFrameMetadata`로 복원
- 원본 frame에서 ROI crop 생성
- crop detection bbox를 원본 frame 좌표로 복원
- periodic full-frame check detection을 같은 결과에 병합
- ROI YOLO metric JSON 저장

## 다음 Task와의 연결

Task 7에서는 Task 5의 `full_frame.jsonl`, Task 6의 `roi_yolo.jsonl`, `rule_roi.jsonl`, `gate_decisions.jsonl`, 그리고 각 metrics JSON을 사용해 recall 유지율, ROI containment, workload reduction, latency report를 계산한다.

## 알려진 제한사항

- Task 6은 ROI crop 결과와 periodic full-frame check 결과를 같은 JSONL에 함께 저장하지만, 중복 detection 제거나 NMS 병합은 아직 수행하지 않는다.
- 실제 YOLO 실행에는 dataset과 `yolov8n.pt` weight가 필요하다.
- GT annotation 기반 metric은 Task 7에서 확장한다.
