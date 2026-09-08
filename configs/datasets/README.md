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

Phase 1.1 validation primarily uses:

- `physicalai/physicalai_row0709_after3m.yaml` for crowded person ROI validation.
- `ua_detrac/ua_detrac_mvi_40204.yaml` for vehicle ROI validation.
- `samples/opencv_vtest.yaml` for lightweight end-to-end checks.

Phase 1.2 validation uses:

- `physicalai/physicalai_row0709_after3m.yaml` as the main ROI improvement dataset.
- `ua_detrac/ua_detrac_mvi_39361.yaml` as the secondary vehicle/traffic cross-check dataset.

Generated or local-only dataset configs should be placed under the closest source folder. For example, PhysicalAI row downloads should write to `physicalai/`, while internal ad hoc samples can live under `samples/`.
