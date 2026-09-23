# Quick Start

새 환경에서 repository의 기본 동작을 확인하는 최소 절차입니다. 모든 명령은 repository root에서 실행합니다.

## 1. 환경 준비

Python 3.11 이상을 권장합니다.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

환경에서 `python` 명령이 없다면 `python3`를 사용합니다.

## 2. Unit Test

외부 dataset이나 model weight 없이 실행할 수 있습니다.

```bash
python -m unittest discover -s tests
```

## 3. Synthetic Smoke Run

Synthetic fixed-camera video를 생성합니다.

```bash
python tools/data/create_smoke_video.py
```

생성된 stream을 먼저 확인할 수 있습니다.

```bash
python experiments/inspect_dataset_stream.py \
  --config configs/datasets/base/smoke.yaml \
  --limit 5
```

ROI generator를 60 frame 실행합니다.

```bash
python experiments/run_rule_roi_baseline.py \
  --dataset-config configs/datasets/base/smoke.yaml \
  --roi-generator-config configs/roi_generator/base/smoke.yaml \
  --roi-output outputs/roi_metadata/smoke_rule_roi.jsonl \
  --frame-output outputs/roi_metadata/smoke_gate_decisions.jsonl \
  --limit 60
```

예상 output:

```text
data/smoke/fixed_camera_motion.mp4
outputs/roi_metadata/smoke_rule_roi.jsonl
outputs/roi_metadata/smoke_gate_decisions.jsonl
```

여기까지 성공하면 dataset stream, ROI signal/policy, metadata serialization 기본 경로가 동작하는 상태입니다.

## 4. 공개 Sample Video

OpenCV VTest sample을 내려받습니다.

```bash
python tools/datasets/download_sample_data.py --dataset opencv-vtest
```

ROI metadata만 빠르게 확인하려면 다음을 실행합니다.

```bash
python experiments/run_rule_roi_baseline.py \
  --dataset-config configs/datasets/samples/opencv_vtest.yaml \
  --roi-generator-config configs/roi_generator/base/default.yaml \
  --limit 30
```

## 5. E2E YOLO Validation

아래 실행은 첫 실행 시 Ultralytics model weight를 내려받을 수 있으므로 network 연결이 필요합니다. CPU에서도 실행할 수 있지만 GPU보다 느립니다.

```bash
python experiments/run_e2e_inference_validation.py \
  --dataset-config configs/datasets/samples/opencv_vtest.yaml \
  --roi-generator-config configs/roi_generator/legacy/profile_balanced.yaml \
  --model-config configs/models/yolo_default.yaml \
  --experiment-name opencv_vtest_balanced \
  --limit 120 \
  --render-limit 30
```

결과는 다음 위치에 생성됩니다.

```text
outputs/e2e_inference_validation/<run_id>/
  manifest.json
  detections/
  roi_metadata/
  reports/
  visualizations/
```

## 다음 단계

- 다른 dataset 준비: [`dataset_setup.md`](dataset_setup.md)
- ROI proposal과 GT 비교: [`roi_proposal_validation.md`](roi_proposal_validation.md)
- E2E 옵션 설명: [`e2e_inference_validation.md`](e2e_inference_validation.md)
- 결과 시각화: [`visualization.md`](visualization.md)
- Phase 1.3 matrix 재실행: [`phase1_3_experiment_matrix.md`](phase1_3_experiment_matrix.md)

전체 실험을 다시 실행하기 전에 [`../current_status.md`](../current_status.md)의 dataset별 해석 제한과 oracle/non-oracle 구분을 확인합니다.
