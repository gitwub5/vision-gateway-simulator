# Task 7. Evaluation 구현 정리

## 목적

Task 7의 목적은 Task 5 full-frame baseline과 Task 6 ROI-gated inference 결과를 비교해 Phase 1의 핵심 검증 지표를 계산하고 report로 저장하는 것이다.

```text
full_frame.jsonl + roi_yolo.jsonl
full_frame_metrics.json + roi_yolo_metrics.json
rule_roi.jsonl + gate_decisions.jsonl
    ↓
comparison_report.json
comparison_report.md
```

## 변경한 주요 파일

- `evaluation/comparison_report.py`
- `evaluation/detection_metrics.py`
- `evaluation/roi_containment.py`
- `evaluation/workload_metrics.py`
- `evaluation/latency_metrics.py`
- `evaluation/__init__.py`
- `experiments/compare_results.py`
- `tests/test_evaluation.py`
- `docs/plan/phase1_implementation_plan.md`
- `README.md`

## 핵심 설계 결정

### Full-frame YOLO를 pseudo reference로 사용

현재 annotation loader는 확장 지점만 있고 GT 기반 metric은 아직 준비되지 않았다.

그래서 Task 7에서는 Task 5의 `full_frame.jsonl`을 pseudo reference로 사용하고, 같은 `camera_id`, `frame_id`, `class_name`의 ROI-gated detection과 IoU 기준으로 greedy matching한다.

기본 IoU threshold는 `0.5`다.

### ROI containment rate

ROI containment는 full-frame reference detection bbox가 같은 frame의 ROI 중 하나에 완전히 포함되는지 계산한다.

이 지표는 ROI crop이 객체를 놓치지 않을 만큼 충분히 잡혔는지 확인하기 위한 ROI 품질 지표다.

### Workload reduction

Task 5와 Task 6 metrics JSON을 비교해 다음 값을 계산한다.

- YOLO 호출 수 감소율
- YOLO 입력 픽셀 면적 감소율

계산식:

```text
reduction = (baseline - candidate) / baseline
```

baseline은 full-frame YOLO, candidate는 ROI-gated YOLO다.

### ROI 통계와 gate latency

`rule_roi.jsonl`과 `gate_decisions.jsonl`에서 다음 값을 계산한다.

- 평균 ROI 수
- 평균 ROI 면적 비율
- 평균 gate latency
- 최대 gate latency

### Report 형식

Task 7은 JSON과 Markdown report를 함께 저장한다.

```text
outputs/reports/comparison_report.json
outputs/reports/comparison_report.md
```

JSON은 후속 자동 분석용이고, Markdown은 사람이 빠르게 확인하는 용도다.

## 실행 방법

Task 4~6 산출물이 먼저 필요하다.

```bash
python experiments/run_rule_roi_baseline.py
python experiments/run_full_frame_baseline.py
python experiments/run_roi_yolo_inference.py
```

비교 report 생성:

```bash
python experiments/compare_results.py \
  --full-frame-detections outputs/detections/full_frame.jsonl \
  --roi-detections outputs/detections/roi_yolo.jsonl \
  --full-frame-metrics outputs/reports/full_frame_metrics.json \
  --roi-metrics outputs/reports/roi_yolo_metrics.json \
  --roi-metadata outputs/roi_metadata/rule_roi.jsonl \
  --frame-metadata outputs/roi_metadata/gate_decisions.jsonl \
  --report-json outputs/reports/comparison_report.json \
  --report-markdown outputs/reports/comparison_report.md
```

IoU threshold 변경:

```bash
python experiments/compare_results.py --iou-threshold 0.4
```

## 검증 방법

```bash
python3 -m compileall common data_loader npx_emulator gpu_inference evaluation experiments tests tools
python3 -m unittest tests.test_evaluation
python3 experiments/compare_results.py --help
```

검증 항목:

- detection IoU 계산
- full-frame reference 대비 ROI-gated pseudo recall 계산
- ROI containment rate 계산
- workload reduction 계산
- gate latency 계산
- comparison JSON/Markdown report 생성

## 다음 Task와의 연결

Task 8에서는 Task 7 report와 detection/ROI metadata를 사용해 ROI overlay, full-frame vs ROI-gated detection 비교 이미지, 실패 사례 시각화를 생성한다.

## 알려진 제한사항

- 현재 recall은 GT annotation 기반 recall이 아니라 full-frame YOLO pseudo reference 대비 recall이다.
- ROI-gated detection 중복 제거 또는 NMS 병합은 Task 7에서 수행하지 않는다.
- mAP, class별 AP, GT 기반 metric은 annotation loader가 준비된 뒤 확장한다.
