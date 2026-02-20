# Testing Review Report: f0-readiness-check

## Scope

- `tests/api/v4/test_readiness.py`
- `tests/unit/schemas/test_readiness_schemas.py`
- `tests/unit/services/test_readiness_service.py`

## Summary

- Critical: 0
- High: 0
- Medium: 0
- Low: 2

## Findings

### Low

1. No test covers English-mode keyword matching behavior.
- File: `tests/unit/services/test_readiness_service.py:60`
- Detail:
  - Current tests verify determinism and self-level effects, but do not assert behavior for English syllabus text.
  - This leaves the case-sensitive keyword issue undetected.
- Recommended test:
  - Add a unit test where syllabus includes `"prerequisite"`/`"essay"` in varied cases and assert difficulty/recommendation outputs are triggered.

2. No direct boundary test for score clamping (`0..100`) under extreme inputs.
- File: `tests/unit/services/test_readiness_service.py:30`
- Detail:
  - There is a generic range assertion, but no targeted test that intentionally pushes score above 100 (or near 0) to verify clamp behavior.
- Recommended test:
  - Add explicit high-signal payload test (long text + multiple signal keywords + low self-level) and assert returned score is exactly `100` when over threshold.

## Existing Strengths

- API contract tests cover 200/400/401 and determinism.
- Schema tests cover unknown fields, invalid levels, and term minimum constraints.
- Service tests cover deterministic behavior and self-level adjustment direction.
