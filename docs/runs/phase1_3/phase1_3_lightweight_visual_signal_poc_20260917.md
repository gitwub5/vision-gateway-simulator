# Phase 1.3-E Lightweight Visual Signal POC - 2026-09-17

## Scope

Phase 1.3-E에서는 motion map 없이 단일 RGB frame에서 계산 가능한 cheap visual cue가 ROI 후보를 만들 수 있는지 확인했다.

이 run은 detector나 semantic model을 쓰지 않고, 아래 경량 신호만 사용한다.

- edge density
- texture variance
- Laplacian texture
- edge + texture hybrid

공통 조건:

- Frame limit: 120
- Grid: 32 x 18 cells
- Output root: `outputs/lightweight_visual_signal_poc/`
- Matrix root: `outputs/lightweight_visual_signal_matrices/phase1_3_lightweight_visual_signal_20260917_104336`
- Profiles:
  - `edge_top_10`
  - `edge_top_20`
  - `texture_top_10`
  - `texture_top_20`
  - `hybrid_top_10`
  - `hybrid_top_20`
  - `hybrid_top_20_dilate1`

## Implementation

Added:

- `evaluation/reports/lightweight_visual_signal.py`
- `experiments/phase1_3/run_lightweight_visual_signal_poc.py`
- `experiments/phase1_3/run_lightweight_visual_signal_matrix.py`
- `tests/evaluation_tests/test_lightweight_visual_signal_report.py`

The runner computes per-frame cell scores from grayscale edge/texture signals, selects top-scoring cells, and evaluates center/bbox containment against target GT.

## Matrix Runs

| Coverage Group | Run root |
|---|---|
| Traffic / parking | `outputs/lightweight_visual_signal_poc/phase1_3_traffic_ua_detrac_mvi_39361_lightweight_visual_signal_20260917_104336` |
| Logistics / smart factory | `outputs/lightweight_visual_signal_poc/phase1_3_logistics_physicalai_row0709_after3m_lightweight_visual_signal_20260917_104336` |
| Surveillance / security | `outputs/lightweight_visual_signal_poc/phase1_3_surveillance_mot17_04_lightweight_visual_signal_20260917_104336` |
| Retail / space analytics | `outputs/lightweight_visual_signal_poc/phase1_3_retail_mall_dataset_lightweight_visual_signal_20260917_104336` |
| General camera-motion stress | `outputs/lightweight_visual_signal_poc/phase1_3_general_visdrone_uav0000086_lightweight_visual_signal_20260917_104336` |

## Summary

Lightweight visual signals are weak as standalone ROI generators. Top 10-20% edge/texture cells usually miss most bbox-level target coverage. One-cell dilation improves recall but expands selected area to roughly 40-56%, reducing the practical input-area benefit.

| Dataset | Best compact non-dilated profile | Selected area | Center GT recall | BBox GT recall | Interpretation |
|---|---|---:|---:|---:|---|
| Traffic / UA-DETRAC | `texture_top_20` | 0.200 | 0.194 | 0.000 | Visual texture does not localize vehicles well in this segment. |
| Logistics / PhysicalAI | `edge_top_20` | 0.200 | 0.152 | 0.017 | Static/tracker signals are much stronger than edge/texture here. |
| Surveillance / MOT17Det | `hybrid_top_20` | 0.200 | 0.427 | 0.036 | Crowd regions are partially correlated with texture, but bbox containment is low. |
| Retail / Mall | `hybrid_top_20` | 0.200 | 0.466 | 0.062 | Useful as a weak crowd-density hint, not a crop policy. |
| General / VisDrone | `texture_top_20` | 0.200 | 0.625 | 0.092 | Texture helps find busy regions, but bbox containment remains low without dilation. |

Dilated hybrid result:

| Dataset | Profile | Selected area | Center GT recall | BBox GT recall |
|---|---|---:|---:|---:|
| Traffic / UA-DETRAC | `hybrid_top_20_dilate1` | 0.559 | 0.822 | 0.067 |
| Logistics / PhysicalAI | `hybrid_top_20_dilate1` | 0.397 | 0.546 | 0.143 |
| Surveillance / MOT17Det | `hybrid_top_20_dilate1` | 0.535 | 0.831 | 0.464 |
| Retail / Mall | `hybrid_top_20_dilate1` | 0.541 | 0.843 | 0.749 |
| General / VisDrone | `hybrid_top_20_dilate1` | 0.518 | 0.713 | 0.598 |

## Full Matrix Pointer

Full generated table:

- `outputs/lightweight_visual_signal_matrices/phase1_3_lightweight_visual_signal_20260917_104336/summary.md`

## Findings

1. Edge/texture/hybrid cell scores should not be promoted as standalone ROI gate policies.
2. BBox containment is low for non-dilated top-k cells, even when center containment is moderate.
3. Dilation makes the signal more useful in Mall, MOT17Det, and VisDrone, but selected area rises above 50% in several cases.
4. Traffic and PhysicalAI are better served by static prior, tracker memory, or domain-specific geometry than by raw edge/texture.
5. Lightweight visual signals remain useful as secondary weighting terms inside a hybrid gate, especially for clutter/crowd/busy-region hints.

## Next Implication

Carry lightweight visual signal forward only as a hybrid component:

- static prior + lightweight visual score
- tracker memory + edge/texture fallback
- objectness/semantic-lightweight scan as a stronger successor to raw edge/texture
- ROI budgeted merge, because dilation quickly expands area

## Verification

- `.venv/bin/python -m unittest tests.evaluation_tests.test_lightweight_visual_signal_report`
- `.venv/bin/python -m py_compile evaluation/reports/lightweight_visual_signal.py experiments/phase1_3/run_lightweight_visual_signal_poc.py experiments/phase1_3/run_lightweight_visual_signal_matrix.py tests/evaluation_tests/test_lightweight_visual_signal_report.py`
- `.venv/bin/python experiments/phase1_3/run_lightweight_visual_signal_matrix.py ...`

