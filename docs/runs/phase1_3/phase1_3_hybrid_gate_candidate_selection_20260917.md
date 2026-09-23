# Phase 1.3-G Hybrid Gate Candidate Selection

Date: 2026-09-17

## Scope

Phase 1.3-G는 B-F POC 결과를 조합해서 600-frame validation으로 올릴 hybrid ROI Gate 후보를 고르는 단계다.

이 단계에서는 새 runtime gate를 구현하지 않고, 기존 summary artifact를 기반으로 domain/scene별 후보를 선정한다.

입력 summary:

- Static Zone / Camera Prior: `outputs/static_zone_prior_matrices/phase1_3_static_zone_prior_20260916_155527/summary.json`
- Tracker Memory: `outputs/tracker_memory_matrices/phase1_3_tracker_memory_20260917_103714/summary.json`
- Lightweight Visual Signal: `outputs/lightweight_visual_signal_matrices/phase1_3_lightweight_visual_signal_20260917_104336/summary.json`
- Temporal Gate: `outputs/temporal_gate_matrices/phase1_3_temporal_gate_20260916_152806/summary.json`
- Compression Signal: `outputs/compression_signal_matrices/phase1_3_compression_signal_20260917_105124/summary.json`

## Output

Selection output:

- `outputs/hybrid_gate_selection/phase1_3_hybrid_gate_candidate_selection_20260917`
- `outputs/hybrid_gate_selection/phase1_3_hybrid_gate_candidate_selection_20260917/reports/hybrid_gate_selection_report.md`

추가한 구현:

- `evaluation/reports/hybrid_gate_selection.py`
- `experiments/phase1_3/run_hybrid_gate_candidate_selection.py`
- `tests/evaluation_tests/test_hybrid_gate_selection_report.py`

## Candidate Families

| Candidate | Status | Target |
|---|---|---|
| `static_zone_prior + tracker_memory + temporal_refresh_guard` | shortlist | Logistics/PhysicalAI, VisDrone stress |
| `static_zone_prior + lightweight_visual_priority` | secondary | Retail/Mall, Surveillance/MOT17 |
| `lane_or_scale_prior + velocity_tracker` | needs_new_probe | Traffic/UA-DETRAC |
| `compression_signal` | deferred | Encoded RTSP/video integration |

## Domain Recommendations

| Domain axis | Dataset | Recommendation | Confidence |
|---|---|---|---|
| Traffic / parking | `phase1_3_traffic_ua_detrac_mvi_39361` | `lane_or_scale_prior + velocity_tracker` | needs_new_probe |
| Logistics / smart factory | `phase1_3_logistics_physicalai_row0709_after3m` | `static_zone_prior + tracker_memory + temporal_refresh_guard` | high |
| Surveillance / security | `phase1_3_surveillance_mot17_04` | `static_zone_prior + lightweight_visual_priority` | low |
| Retail / space analytics | `phase1_3_retail_mall_dataset` | `static_zone_prior + lightweight_visual_priority` | medium |
| General multi-class stress | `phase1_3_general_visdrone_uav0000086` | `static_zone_prior + tracker_memory + temporal_refresh_guard` | high |

## Interpretation

### 1. Static prior should be the spatial anchor

Static Zone / Camera Prior consistently produced strong center coverage. However, bbox containment requires dilation/margin, so static prior should not be treated as final detector ROI by itself.

Recommended role:

- camera-specific spatial seed
- region prior for ranking, packing, or full-frame switch
- static mask for excluding impossible background

### 2. Tracker memory is promising only when recall stays high

Tracker memory is strongest on PhysicalAI and selected VisDrone segment.

- PhysicalAI: `refresh_10_margin_30` reached high recall with strong effective input reduction.
- VisDrone: tracker memory recall is high, but ROI count is large, so packing/budget is mandatory.
- MOT17 and Mall have dense person scenes where ROI count risk is high.
- UA-DETRAC traffic is weak under simple hold-memory and needs velocity/scale modeling.

Recommended role:

- short-term detector result persistence
- low-frequency detector refresh
- stale-track and ROI budget control

### 3. Lightweight signal is secondary, not primary

Raw edge/texture/hybrid signal is not strong enough as final ROI generator. It is still useful as a secondary priority score in dense/static-prior regions, especially Mall, MOT17, and VisDrone.

Recommended role:

- busy-region priority score
- tie-breaker under ROI budget
- input to later lightweight objectness successor

### 4. Temporal gate should be a guard, not a primary selector

Most official samples contain targets in every frame. Standalone frame skip quickly becomes recall loss. Temporal gate should only bound refresh cadence after a spatial/tracker candidate already exists.

Recommended role:

- refresh cadence guard
- detector call rate controller
- max stale duration limiter

### 5. Traffic needs a new probe

Traffic/UA-DETRAC should not be forced into the current static+tracker or static+lightweight combinations.

Observed issue:

- static center prior is strong, but bbox containment is low.
- simple hold-memory tracker recall is weak.
- lightweight visual signal is too weak as detector ROI.

Next traffic candidate should be:

- lane/road-region prior
- scale-aware ROI expansion by perspective
- velocity/Kalman prediction
- object-size bucket aware ROI margin

## Decision

600-frame validation으로 바로 올릴 후보:

1. `static_zone_prior + tracker_memory + temporal_refresh_guard`
   - 대상: PhysicalAI, VisDrone stress
   - 추가 조건: non-oracle detector refresh, ROI packing, stale-track handling

2. `static_zone_prior + lightweight_visual_priority`
   - 대상: Mall, MOT17
   - 추가 조건: budgeted priority simulation, bbox-safe dilation sweep

새 probe가 필요한 후보:

3. `lane_or_scale_prior + velocity_tracker`
   - 대상: UA-DETRAC traffic
   - 이유: 현재 조합 후보로는 traffic bbox ROI 품질이 부족함

Deferred:

4. `compression_signal`
   - encoded RTSP/video metadata 접근 가능한 integration 환경에서 재검증

## Verification

- `python -m unittest tests.evaluation_tests.test_hybrid_gate_selection_report`
- `python -m py_compile evaluation/reports/hybrid_gate_selection.py experiments/phase1_3/run_hybrid_gate_candidate_selection.py tests/evaluation_tests/test_hybrid_gate_selection_report.py`
- `python experiments/phase1_3/run_hybrid_gate_candidate_selection.py --run-id phase1_3_hybrid_gate_candidate_selection_20260917`
