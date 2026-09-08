# Dataset Configs

Dataset configs are grouped by use and upstream source so validation commands stay readable.

```text
configs/datasets/
  base/
    default.yaml
    smoke.yaml
  samples/
    opencv_vtest.yaml
  physicalai/
    physicalai_row0709.yaml
    physicalai_row0709_after3m.yaml
  ua_detrac/
    ua_detrac_mvi_39031.yaml
    ua_detrac_mvi_39361.yaml
    ua_detrac_mvi_39051.yaml
    ua_detrac_mvi_40204.yaml
  od_virat/
    od_virat_tiny.yaml
```

Use `base/default.yaml` for generic local development and `base/smoke.yaml` for quick smoke checks.

Dataset setup tools are grouped under `tools/datasets/`. Root-level `tools/*.py`
entries are compatibility wrappers for older commands.

Phase 1.1 validation primarily uses:

- `physicalai/physicalai_row0709_after3m.yaml` for crowded person ROI validation.
- `ua_detrac/ua_detrac_mvi_40204.yaml` for vehicle ROI validation.
- `samples/opencv_vtest.yaml` for lightweight end-to-end checks.

Phase 1.2 validation uses:

- `physicalai/physicalai_row0709_after3m.yaml` as the main ROI improvement dataset.
- `ua_detrac/ua_detrac_mvi_39361.yaml` as the secondary vehicle/traffic cross-check dataset.

Phase 1.3 validation should expand by scene/domain coverage instead of adding more sequences from the same source:

- Keep `physicalai/physicalai_row0709_after3m.yaml` as the Phase 1.2 comparable indoor/person baseline.
- Use only one `UA-DETRAC MVI_*` sequence in the official Phase 1.3 matrix, initially `ua_detrac/ua_detrac_mvi_39361.yaml`.
- Do not include `od_virat/od_virat_tiny.yaml` in the official Phase 1.3 dataset plan; it remains a historical annotation-loader sanity dataset only.
- Add MOTChallenge `MOT17-04` for surveillance/security, AI City Challenge 2023 Track 4 for retail/space analytics, and VisDrone-VID validation data for the general multi-class stress check.
- Use `tools/datasets/download_mot17.py`, `tools/datasets/download_ai_city_2023_track4.py`, and `tools/datasets/download_visdrone_vid.py` to prepare those public candidates.
- Record scene conditions in `validation.notes` first; add structured `validation.scene_conditions` only after the metadata shape stabilizes.

Generated or local-only dataset configs should be placed under the closest source folder. For example, PhysicalAI row downloads should write to `physicalai/`, while internal ad hoc samples can live under `samples/`.
