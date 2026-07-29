# Task 8. Visualization 구현 정리

## 목적

Task 8의 목적은 Task 4~7 산출물을 사람이 확인할 수 있는 이미지로 렌더링하는 것이다.

```text
DatasetStream
rule_roi.jsonl
full_frame.jsonl
roi_yolo.jsonl
    ↓
ROI overlay / detection comparison / failure case images
```

## 변경한 주요 파일

- `visualization/renderer.py`
- `visualization/__init__.py`
- `experiments/render_visualizations.py`
- `tests/test_visualization.py`
- `docs/plan/phase1_implementation_plan.md`
- `README.md`

## 핵심 설계 결정

### 산출물 디렉터리 분리

Task 8은 `outputs/visualizations/` 아래에 목적별 이미지를 저장한다.

```text
outputs/visualizations/roi_overlay/
outputs/visualizations/comparison/
outputs/visualizations/failures/
```

### ROI overlay

ROI overlay 이미지는 원본 frame 위에 Task 4의 ROI box와 Task 6의 ROI-gated detection을 함께 그린다.

이 이미지는 ROI 생성 결과가 YOLO inference 입력으로 적절했는지 빠르게 확인하기 위한 것이다.

### Full-frame vs ROI-gated comparison

comparison 이미지는 같은 원본 frame을 좌우 패널로 나눠 보여준다.

```text
left:  full-frame YOLO detections
right: ROI boxes + ROI-gated YOLO detections
```

이 구조는 Task 7의 pseudo recall 결과를 시각적으로 확인하기 위한 것이다.

### 실패 사례 저장

Task 8은 full-frame reference detection과 ROI-gated detection을 같은 `camera_id`, `frame_id`, `class_name` 기준으로 IoU matching한다.

기본 IoU threshold는 `0.5`다.

matching되지 않은 full-frame detection이 있으면 해당 frame을 failure case 이미지로 저장한다.

## 실행 방법

Task 4~7 산출물이 먼저 필요하다.

```bash
python experiments/run_rule_roi_baseline.py
python experiments/run_full_frame_baseline.py
python experiments/run_roi_yolo_inference.py
python experiments/compare_results.py
```

시각화 생성:

```bash
python experiments/render_visualizations.py \
  --dataset-config configs/dataset.yaml \
  --roi-metadata outputs/roi_metadata/rule_roi.jsonl \
  --full-frame-detections outputs/detections/full_frame.jsonl \
  --roi-detections outputs/detections/roi_yolo.jsonl \
  --output-root outputs/visualizations
```

일부 frame만 렌더링:

```bash
python experiments/render_visualizations.py --render-limit 20
```

실패 사례 IoU threshold 변경:

```bash
python experiments/render_visualizations.py --iou-threshold 0.4
```

## 검증 방법

```bash
python3 -m compileall common data_loader npx_emulator gpu_inference evaluation visualization experiments tests tools
python3 -m unittest tests.test_visualization
python3 experiments/render_visualizations.py --help
```

실제 smoke 실행 결과와 대표 이미지는 `docs/smoke_test_visualization_result.md`에 기록했다.

검증 항목:

- full-frame reference detection 대비 missed detection 탐지
- ROI overlay 저장 흐름
- full-frame vs ROI-gated comparison 저장 흐름
- failure case 저장 흐름
- OpenCV/NumPy 미설치 시 안내 에러 경로 유지

## 다음 Task와의 연결

Task 8은 Phase 1의 마지막 구현 Task다. 이후에는 실제 fixed-camera dataset에서 Task 4~8 end-to-end 산출물을 생성하고, 공유 가능한 산출물 위치와 제한사항을 기록한다.

## 알려진 제한사항

- failure case는 full-frame YOLO pseudo reference 기준이다. GT annotation 기반 실패 사례 분류는 annotation loader가 준비된 뒤 확장한다.
- 이미지는 `.jpg`로 저장한다.
- 중복 detection 제거 또는 NMS 병합은 visualization 단계에서 수행하지 않는다.
