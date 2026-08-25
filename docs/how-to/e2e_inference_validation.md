# E2E Inference Validation

E2E inference validation은 ROI gate와 YOLO inference를 함께 실행해 downstream compatibility를 확인한다.

Repo root에서 실행한다.

## OpenCV VTest Quick

```bash
python experiments/run_e2e_inference_validation.py \
  --dataset-config configs/datasets/samples/opencv_vtest.yaml \
  --roi-generator-config configs/roi_generator/legacy/profile_balanced.yaml \
  --model-config configs/models/yolo_default.yaml \
  --experiment-name opencv_vtest_balanced \
  --limit 120 \
  --render-limit 30
```

## UA-DETRAC Vehicle Quick

```bash
python experiments/run_e2e_inference_validation.py \
  --dataset-config configs/datasets/ua_detrac/ua_detrac_mvi_40204.yaml \
  --roi-generator-config configs/roi_generator/legacy/profile_balanced.yaml \
  --model-config configs/models/yolo_default.yaml \
  --experiment-name ua_detrac_mvi_40204_balanced \
  --limit 120 \
  --render-limit 30
```

## Outputs

```text
outputs/e2e_inference_validation/<run_id>/
  detections/
  roi_metadata/
  reports/
  visualizations/
  manifest.json
```

실행 결과 요약과 해석은 `docs/runs/`에 기록한다.
