# Run Logs

이 폴더는 실제 검증/실험 실행 결과를 기록한다.

`docs/plan/`은 앞으로 무엇을 어떻게 검증할지 쓰는 계획 문서이고, `docs/runs/`는 이미 실행한 결과와 해석을 남기는 로그 문서다. 대용량 `outputs/` artifact는 Git에 포함하지 않고, run id와 report 경로만 기록한다.

## Structure

```text
docs/runs/
  phase1/
  phase1_1/
  phase1_2/
  phase1_3/
```

## Naming

| Pattern | Use |
|---|---|
| `phase*/phase<phase>_<stage>_<topic>_<yyyymmdd>.md` | 특정 phase/stage 실험 결과 |
| `phase*/phase<phase>_<dataset>_<topic>_<yyyymmdd>.md` | dataset 중심 결과 |
| `legacy_*.md` | 과거 로그를 보존할 때 |

## Current Logs

| File | Scope |
|---|---|
| `phase1/phase1_validation_runs.md` | Phase 1 초반 validation run index. 새 실험은 가능하면 별도 파일에 기록 |
| `phase1_1/phase1_1_a1_roi_policy_baselines_20260819.md` | Phase 1.1 A1 ROI policy matrix, sweep, selected profile 결과 |
| `phase1_1/phase1_1_stage_d_final_policy_selection_20260825.md` | Phase 1.1 final policy selection 결과 |
| `phase1_1/phase1_1_visual_review_artifacts_20260825.md` | Phase 1.1 visual review artifact 생성 기록 |
| `phase1_1/phase1_1_stage_b_tile_dilation_probe_20260826.md` | Stage B tile dilation tuning probe 결과 |
| `phase1_1/phase1_1_stage_b_c_true_tile_visual_overview_20260826.md` | Phase 1.1 Stage B/C 실제 tile trace 기반 시각화 비교 결과 |
| `phase1_2/phase1_2_readiness_baselines_20260826.md` | Phase 1.2 공식 tile-trace baseline, provenance, 자동 비교 결과 |
| `phase1_3/phase1_3_dataset_readiness_smoke_20260909.md` | Phase 1.3 dataset readiness smoke와 baseline failure 해석 |
| `phase1_3/phase1_3_baseline_failure_map_20260916.md` | Phase 1.3 5-domain current pipeline baseline failure map |
| `phase1_3/phase1_3_temporal_gate_poc_20260916.md` | Phase 1.3-B temporal gate POC 결과와 해석 |
| `phase1_3/phase1_3_static_zone_prior_poc_20260916.md` | Phase 1.3-C static zone / camera prior POC 결과와 해석 |
| `phase1_3/phase1_3_tracker_memory_poc_20260917.md` | Phase 1.3-D feedback / tracker memory POC 결과와 해석 |
| `phase1_3/phase1_3_lightweight_visual_signal_poc_20260917.md` | Phase 1.3-E lightweight visual signal POC 결과와 해석 |
| `phase1_3/phase1_3_compression_signal_poc_20260917.md` | Phase 1.3-F compression signal prototype 결과와 해석 |
| `phase1_3/phase1_3_hybrid_gate_candidate_selection_20260917.md` | Phase 1.3-G hybrid gate candidate selection 결과와 해석 |
| `phase1_3/phase1_3_traffic_velocity_prior_probe_20260917.md` | Phase 1.3-H traffic velocity / scale prior probe 결과와 해석 |
| `phase1_3/phase1_3_traffic_road_region_prior_probe_20260917.md` | Phase 1.3-I traffic road / lane region prior probe 결과와 해석 |
| `phase1_3/phase1_3_hybrid_family_600frame_validation_20260917.md` | Phase 1.3-J/K shortlisted hybrid family(static+tracker+guard, static+lightweight) 600-frame validation 결과 |
| `phase1_3/phase1_3_final_domain_recommendation_matrix_20260917.md` | Phase 1.3-M 최종 domain/scene ROI Gate recommendation matrix, traffic 방향 확정, Phase 1.3 종료 판정 |
