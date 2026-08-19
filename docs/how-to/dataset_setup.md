# Dataset Setup

Repo root에서 실행한다.

## List Sample Datasets

```bash
python tools/download_sample_data.py --list
```

## OpenCV VTest

```bash
python tools/download_sample_data.py --dataset opencv-vtest
```

## UA-DETRAC

UA-DETRAC은 수동으로 image archive와 annotation XML archive를 받아 `data/ua_detrac/` 아래에 압축 해제한다.

Phase 1.1 vehicle-only baseline config:

```text
configs/datasets/ua_detrac_mvi_40204.yaml
```

Expected paths:

```text
data/ua_detrac/DETRAC-Images/DETRAC-Images/MVI_40204/
data/ua_detrac/DETRAC-Train-Annotations-XML/DETRAC-Train-Annotations-XML/MVI_40204.xml
```

## PhysicalAI Smart Spaces

Row 단위로 선택 다운로드한다.

```bash
python tools/download_physicalai_row.py --row-id 709 --dry-run
python tools/download_physicalai_row.py --row-id 709
```

Phase 1.1 person crowded baseline config:

```text
configs/datasets/physicalai_row0709_after3m.yaml
```

## Inspect Dataset Stream

```bash
python experiments/inspect_dataset_stream.py \
  --config configs/datasets/physicalai_row0709_after3m.yaml \
  --limit 5
```
