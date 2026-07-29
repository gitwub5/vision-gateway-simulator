# Task 5. Full-frame YOLO Baseline 구현 정리

## 목적

Task 5의 목적은 모든 입력 frame을 YOLOv8에 넣는 full-frame baseline을 만들고, 이후 ROI-gated inference와 비교할 기준 결과를 저장하는 것이다.

```text
DatasetStream
    ↓
FramePacket
    ↓
FullFrameYoloRunner
    ↓
Detection JSONL + full-frame metrics
```

## 변경한 주요 파일

- `gpu_inference/yolo_full_frame.py`
- `experiments/run_full_frame_baseline.py`
- `tests/test_yolo_full_frame.py`
- `requirements.txt`
- `docs/plan/phase1_implementation_plan.md`

## 핵심 설계 결정

### `FullFrameYoloRunner`

`FullFrameYoloRunner`는 `FramePacket` iterable을 받아 YOLOv8 inference를 수행하고 `Detection` 목록으로 변환한다.

```python
runner = FullFrameYoloRunner.from_config(yolo_config)
detections = runner.run(stream)
```

이 구조를 둔 이유는 Task 2의 dataset loader와 Task 7의 evaluation이 `FramePacket`과 `Detection` schema만 공유하면 되도록 하기 위해서다.

### Config 기반 실행

YOLO 모델, 입력 크기, confidence threshold, IoU threshold, class filter는 `configs/yolo.yaml`에서 읽는다.

실험 결과에 영향을 주는 값은 문서 규칙에 따라 코드에 고정하지 않고 config로 관리한다.

### Full-frame workload metric

Task 5의 workload 기준은 full-frame baseline이다.

기록 항목:

- `frame_count`
- `yolo_call_count`
- `yolo_input_pixel_area`
- frame별 `latency_ms`
- `average_latency_ms`
- `detection_count`
- 사용한 YOLO config snapshot

ROI-gated workload reduction은 Task 7에서 이 full-frame metric과 ROI metric을 비교해 계산한다.

### Detection JSONL

YOLO 결과는 `common.Detection`으로 변환한 뒤 JSONL로 저장한다.

기본 출력:

```text
outputs/detections/full_frame.jsonl
```

## 실행 방법

의존성 설치:

```bash
pip install -r requirements.txt
```

기본 실행:

```bash
python experiments/run_full_frame_baseline.py \
  --dataset-config configs/dataset.yaml \
  --yolo-config configs/yolo.yaml
```

짧은 구간만 실행:

```bash
python experiments/run_full_frame_baseline.py \
  --dataset-config configs/dataset.yaml \
  --yolo-config configs/yolo.yaml \
  --limit 10
```

## 검증 방법

```bash
python3 -m compileall common data_loader gpu_inference evaluation experiments tests
python3 -m unittest tests.test_yolo_full_frame
```

검증 항목:

- YOLO result가 `Detection` schema로 변환되는지 확인
- class filter가 적용되는지 확인
- full-frame workload metric이 기록되는지 확인
- detection JSONL과 metrics JSON이 생성되는지 확인

## 다음 Task와의 연결

Task 6에서는 Task 4의 ROI metadata를 기준으로 crop YOLO inference를 수행하고, crop 좌표계 detection을 원본 frame 좌표계로 복원한다.

Task 7에서는 Task 5의 `full_frame.jsonl`과 `full_frame_metrics.json`을 ROI-gated 결과와 비교해 recall 유지율과 workload reduction을 계산한다.

## 알려진 제한사항

- `yolov8n.pt` weight가 로컬에 없으면 Ultralytics가 자동 다운로드를 시도할 수 있다.
- 네트워크가 제한된 환경에서는 model weight를 미리 준비해야 한다.
- Task 5는 pseudo baseline 저장이 목적이므로 GT annotation 기반 recall/mAP 계산은 Task 7 이후에 확장한다.
