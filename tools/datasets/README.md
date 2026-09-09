# Dataset Tools

Dataset acquisition is split by upstream source because license, auth, and archive layouts differ.

Google Drive based downloads require `gdown`:

```bash
pip install gdown
```

```bash
python tools/datasets/download_sample_data.py --list
python tools/datasets/download_mot17.py --download-images --extract
python tools/datasets/download_visdrone_vid.py --split val --extract
python tools/datasets/download_mall_dataset.py --extract
python tools/datasets/download_physicalai_row.py --row-id 709 --dry-run
```

`download_ua_detrac.py` accepts manually downloaded archives or direct mirror URLs:

```bash
python tools/datasets/download_ua_detrac.py \
  --images-archive data/ua_detrac/archives/DETRAC-Images.zip \
  --annotations-archive data/ua_detrac/archives/DETRAC-Train-Annotations-XML.zip \
  --extract
```

Prefer the grouped paths above for new docs and scripts.
