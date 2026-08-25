# Phase 1.1 Pre-Stage B Structure Cleanup

## Scope

Stage B 작업 전에 `evaluation/`과 `tests/`의 flat file layout을 도메인별 폴더 구조로 정리했다.

## Evaluation Layout

```text
evaluation/
  metrics/
    class_filter.py
    detection.py
    latency.py
    roi_containment.py
    workload.py
  reports/
    comparison.py
    gt.py
    phase1_summary.py
    roi_proposal.py
  system/
    hardware.py
```

`evaluation/__init__.py`는 기존 top-level public API를 유지한다.

## Test Layout

테스트 하위 폴더는 runtime package 이름과 충돌하지 않도록 `_tests` suffix를 사용한다.

```text
tests/
  common_tests/
  data_loading_tests/
  evaluation_tests/
  gpu_inference_tests/
  roi_generator_tests/
  visualization_tests/
```

`python -m unittest discover -s tests`가 그대로 동작한다.

## Verification

```text
Ran 79 tests in 0.179s
OK
```

Compile check also passed for:

```text
common data_loader evaluation experiments gpu_inference roi_generator tests tools visualization
```
