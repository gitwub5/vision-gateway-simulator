# Documentation Structure

이 디렉터리는 공유 가능한 구현 문서와 로컬 기술 메모를 분리해서 관리한다.

## 공유 문서

| 경로 | 용도 |
|---|---|
| `plan/` | Phase별 구현 계획, 검증 계획, 로드맵 |
| `tasks/phase*/` | Phase별 Task 구현 기록 |
| `sample_data.md` | 검증용 sample data 준비 방법 |
| `smoke_test.md` | smoke test 실행 방법 |
| `smoke_test_visualization_result.md` | smoke visualization 결과 |
| `assets/` | 문서에서 사용하는 이미지 |

## 로컬 문서

`docs/idea/`는 기술적 고민, 검증 가설, 성공 기준 초안, 의사결정 초안, 외부 제품과의 포지셔닝 메모를 두는 개인 작업 공간이다.

이 폴더는 `.gitignore`에 포함되어 Git에 올라가지 않는다. 공유가 필요한 내용은 정리한 뒤 `docs/plan/`의 적절한 문서로 옮긴다.
