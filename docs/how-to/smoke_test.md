# Smoke Test

Synthetic smoke test는 외부 dataset 없이 pipeline이 깨졌는지 빠르게 확인하기 위한 실행 절차다.

Repo root에서 실행한다.

## Create Smoke Video

```bash
python tools/create_smoke_video.py
```

Expected output:

```text
data/smoke/fixed_camera_motion.mp4
```

## Inspect Stream

```bash
python experiments/inspect_dataset_stream.py \
  --config configs/datasets/smoke.yaml \
  --limit 5
```

## ROI Metadata Smoke

```bash
python experiments/run_rule_roi_baseline.py \
  --dataset-config configs/datasets/smoke.yaml \
  --roi-generator-config configs/roi_generator/smoke.yaml \
  --roi-output outputs/roi_metadata/smoke_rule_roi.jsonl \
  --frame-output outputs/roi_metadata/smoke_gate_decisions.jsonl \
  --limit 60
```

Expected outputs:

```text
outputs/roi_metadata/smoke_rule_roi.jsonl
outputs/roi_metadata/smoke_gate_decisions.jsonl
```
