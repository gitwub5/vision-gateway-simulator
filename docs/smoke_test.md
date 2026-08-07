# Fixed-camera Smoke Test

## 목적

Phase 1 개발 중 외부 dataset 없이 pipeline이 깨졌는지 빠르게 확인하기 위한 synthetic fixed-camera smoke test다.

이 영상은 정확도 검증용이 아니다. 실제 ROI 품질, recall, workload reduction 판단은 UA-DETRAC, OD-VIRAT, 또는 사내 고정 CCTV 샘플로 수행한다.

## 생성되는 영상

```text
data/smoke/fixed_camera_motion.mp4
```

특징:

- 고정 배경
- 이동하는 차량 형태 객체
- 잠깐 멈추는 구간
- 이동하는 사람 형태 객체
- 약한 deterministic noise

이 구성으로 다음 동작을 확인할 수 있다.

- Dataset Stream Loader
- Rule-based ROI Gate
- Temporal hold
- ROI metadata 저장
- Frame-level gate decision 저장

## 생성 방법

가상환경을 준비한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

영상 생성:

```bash
python tools/create_smoke_video.py
```

## Loader 확인

```bash
python experiments/inspect_dataset_stream.py \
  --config configs/datasets/smoke.yaml \
  --limit 3
```

## ROI metadata smoke test

```bash
python experiments/run_rule_roi_baseline.py \
  --dataset-config configs/datasets/smoke.yaml \
  --gate-config configs/npx_gate/smoke.yaml \
  --roi-output outputs/roi_metadata/smoke_rule_roi.jsonl \
  --frame-output outputs/roi_metadata/smoke_gate_decisions.jsonl \
  --limit 60
```

예상 산출물:

```text
outputs/roi_metadata/smoke_rule_roi.jsonl
outputs/roi_metadata/smoke_gate_decisions.jsonl
```

## 역할 구분

```text
Synthetic fixed-camera video:
개발 중 smoke/regression test

UA-DETRAC / OD-VIRAT / 사내 CCTV:
실제 Phase 1 validation
```
