# Dataset Setup

Repo root에서 실행한다.

Google Drive로 배포되는 dataset(`VisDrone-VID`)은 `gdown`이 있으면 자동 다운로드할 수 있다.

```bash
pip install gdown
```

## List Sample Datasets

```bash
python tools/datasets/download_sample_data.py --list
```

## OpenCV VTest

```bash
python tools/datasets/download_sample_data.py --dataset opencv-vtest
```

## UA-DETRAC

UA-DETRAC은 수동으로 image archive와 annotation XML archive를 받거나 direct mirror URL을 지정해 `data/ua_detrac/` 아래에 압축 해제한다.

```bash
python tools/datasets/download_ua_detrac.py \
  --images-archive data/ua_detrac/archives/DETRAC-Images.zip \
  --annotations-archive data/ua_detrac/archives/DETRAC-Train-Annotations-XML.zip \
  --extract
```

Phase 1.1 vehicle-only baseline config:

```text
configs/datasets/ua_detrac/ua_detrac_mvi_40204.yaml
```

Expected paths:

```text
data/ua_detrac/DETRAC-Images/DETRAC-Images/MVI_40204/
data/ua_detrac/DETRAC-Train-Annotations-XML/DETRAC-Train-Annotations-XML/MVI_40204.xml
```

## PhysicalAI Smart Spaces

Row 단위로 선택 다운로드한다.

```bash
python tools/datasets/download_physicalai_row.py --row-id 709 --dry-run
python tools/datasets/download_physicalai_row.py --row-id 709
```

## Phase 1.3 Public Datasets

```bash
python tools/datasets/download_mot17.py --download-images --extract
python tools/datasets/download_visdrone_vid.py --split val --extract
python tools/datasets/download_mall_dataset.py --extract
```

VisDrone Google Drive quota가 걸리면 `VisDrone2019-VID-val.zip`을 브라우저로 받은 뒤 아래처럼 추출한다.

```bash
python tools/datasets/download_visdrone_vid.py \
  --split val \
  --archive /path/to/VisDrone2019-VID-val.zip \
  --extract
```

Mall Dataset은 shopping-mall webcam frame sequence와 exhaustive pedestrian head-position GT를 제공한다. bbox GT가 아니므로 Phase 1.3에서는 point containment 또는 documented proxy box 기준으로 해석한다.

```text
configs/datasets/mall/mall_dataset.yaml
```

Phase 1.1 person crowded baseline config:

```text
configs/datasets/physicalai/physicalai_row0709_after3m.yaml
```

## Inspect Dataset Stream

```bash
python experiments/inspect_dataset_stream.py \
  --config configs/datasets/physicalai/physicalai_row0709_after3m.yaml \
  --limit 5
```
