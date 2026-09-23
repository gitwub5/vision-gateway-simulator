# Current Project Status

## 한 줄 요약

Vision Frontend Simulator는 영상 전체를 매번 GPU detector에 전달하는 대신 ROI만 선택적으로 전달하는 Vision Frontend Gate의 가능성과 한계를 검증한 연구용 simulator입니다.

현재 Phase 1.3까지의 탐색이 종료되었으며, 다음 단계에서 구현할 architecture family를 선정한 상태입니다.

## 구현되어 있는 것

- video와 image sequence를 공통 `FramePacket`으로 변환하는 dataset stream
- 여러 공개 dataset의 annotation loader
- frame difference, component, tile 기반 rule-based ROI generator
- temporal hold, periodic full-frame check, feedback, ROI budget/fallback
- full-frame YOLO와 ROI crop YOLO inference
- ROI 좌표의 original frame 좌표계 복원
- ROI containment, detection recall, workload, latency 평가
- JSON/JSONL report와 ROI/detection visualization
- dataset/profile matrix 실행과 결과 비교 도구

## Phase 상태

| Phase | 상태 | 결과 |
|---|---|---|
| Phase 1 | 완료 | loader → ROI gate → YOLO → evaluation → visualization 기본 pipeline 구성 |
| Phase 1.1 | 완료 | component/tile/hybrid policy와 ROI/tile/cost contract 비교 |
| Phase 1.2 | 완료 | boundary rescue, feedback, fallback, budget 개선 후보 검증 |
| Phase 1.3 | 완료 | 5개 domain에서 기존 접근의 failure map을 만들고 다음 architecture 후보 선정 |
| Phase 2 | 미진행 | 선정된 architecture를 non-oracle runtime path로 구현하고 packing을 검증해야 함 |

## Phase 1.3 핵심 결론

기존 motion/tile primary gate는 PhysicalAI indoor warehouse를 제외한 여러 domain에서 안정적인 primary ROI generator로 사용하기 어려웠습니다. Temporal skip, static prior, tracker memory, lightweight visual signal도 단독으로는 충분하지 않았습니다.

다음 단계 후보는 세 family로 정리되었습니다.

| 대상 domain | 다음 architecture family |
|---|---|
| Logistics / smart factory, general multi-class | `static_zone_prior + tracker_memory + temporal_refresh_guard` |
| Surveillance / security, retail / space analytics | `static_zone_prior + lightweight_visual_priority` |
| Traffic / parking | `road/lane segmented prior + entry-zone guard + tracker/refresh + packing` |

세 후보 모두 다음 구현 전에 ROI 수와 면적을 줄이는 merge/packing 및 budget controller가 필요합니다. 상세 근거는 [Phase 1.3 Final Recommendation Matrix](runs/phase1_3/phase1_3_final_domain_recommendation_matrix_20260917.md)에 있습니다.

## 해석 시 주의사항

- 이 저장소는 production runtime이나 hardware implementation이 아닙니다.
- Phase 1.3의 여러 후보는 독립 POC/report 형태이며 모두 `roi_generator/core/`의 runtime path에 통합된 것은 아닙니다.
- tracker/refresh 실험 일부는 ground truth 또는 oracle 성격의 입력을 사용했습니다. 실제 detector feedback을 사용하는 non-oracle 검증이 필요합니다.
- Mall Dataset은 head point를 proxy box로 변환하므로 실제 person bbox recall과 동일하게 해석하면 안 됩니다.
- VisDrone은 이동 카메라 stress test이며 고정 CCTV deployment 성능을 대표하지 않습니다.
- 실험 output과 dataset은 Git에 포함되지 않습니다. 문서의 결과를 재현하려면 각 dataset을 별도로 준비해야 합니다.

## 다음 연구자가 시작할 위치

새 기능을 추가하기 전에 아래 순서를 권장합니다.

1. [Quick Start](how-to/quickstart.md)로 unit test와 synthetic smoke run을 확인합니다.
2. [Architecture](architecture.md)에서 `FramePacket`, `GateDecision`, ROI metadata 계약을 확인합니다.
3. Phase 1.3 최종 recommendation과 관련 run 문서를 읽습니다.
4. 가장 confidence가 높았던 logistics용 `static_zone_prior + tracker_memory + temporal_refresh_guard`를 non-oracle detector refresh로 구현합니다.
5. 공통 ROI merge/packing과 budget controller를 먼저 설계한 뒤 다른 domain으로 확장합니다.

## 유지해야 할 기준

- schema나 config 변경이 기존 report reader와 visualization을 깨지 않는지 unit test로 확인합니다.
- 실험 config, Git revision, 입력 config hash를 manifest에 남깁니다.
- 결과 수치만 기록하지 않고 dataset segment, target class, oracle/non-oracle 여부를 함께 기록합니다.
- 새로운 후보가 기존 baseline보다 recall 또는 cost를 개선하지 못했다면 실패 결과도 `docs/runs/`에 남깁니다.
