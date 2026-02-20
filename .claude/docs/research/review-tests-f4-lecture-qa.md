# Test Review: f4-lecture-qa

## Validation Run

- `uv run pytest -q` -> `102 passed, 1 skipped`
- Coverage summary -> `82%` total
- Coverage hotspots:
  - `app/services/lecture_bm25_store.py` -> `0%`
  - `app/services/lecture_verifier_service.py` -> `52%`
  - `app/services/lecture_answerer_service.py` -> `54%`
  - `app/services/lecture_followup_service.py` -> `55%`
  - `app/services/lecture_retrieval_service.py` -> `56%`

## Findings

### [High] Missing E2E assertion for index persistence allowed a core regression

- Evidence:
  - `tests/api/v4/test_lecture_qa.py:73` test name implies “with index returns answer”, but does not call index build API.
  - `tests/api/v4/test_lecture_qa.py:92` sets `qa_index_built=True` directly in DB, bypassing real index storage path.
  - `tests/api/v4/test_lecture_qa.py:127` only asserts `sources` is a list, not non-empty after index build.
- Risk:
  - Build->ask lifecycle bug shipped without test detection.
- Recommendation:
  - Add true E2E test: create speech events -> call `/index/build` -> call `/ask` -> assert `len(sources) > 0` for a matching query.

### [Medium] Ownership/authorization behavior has a known skipped test

- Evidence:
  - `tests/api/v4/test_lecture_qa.py:363` skipped ownership validation test.
  - `tests/api/v4/test_lecture_qa.py:369` note says current implementation returns 500 due unhandled `ValueError`.
- Risk:
  - Authorization failure path remains unverified and currently maps to server error.
- Recommendation:
  - Convert service exceptions to domain HTTP errors (404/403) and unskip this test.

### [Medium] No tests cover configured OpenAI integration path

- Evidence:
  - QA services contain TODO placeholders in:
    - `app/services/lecture_answerer_service.py:158`
    - `app/services/lecture_verifier_service.py:175`
    - `app/services/lecture_followup_service.py:238`
  - Current tests pass with empty credentials/default paths.
- Risk:
  - Production integration failures (timeouts, malformed responses, parsing errors) are not exercised.
- Recommendation:
  - Add contract tests with mocked OpenAI client responses and failure cases.

### [Medium] Settings API lacks tests for per-user isolation/auth requirements

- Evidence:
  - `tests/api/v4/test_settings.py:13` and `:36` use no auth headers and expect `demo_user`.
- Risk:
  - Multi-user correctness and auth invariants are currently untested.
- Recommendation:
  - After auth integration, add tests for user-bound reads/writes and cross-user isolation.

### [Low] Static quality checks are failing despite green pytest

- Evidence:
  - `uv run ruff check app tests` failed.
  - `uv run mypy app tests` failed with large error count.
- Risk:
  - Test suite can be green while type/lint regressions accumulate.
- Recommendation:
  - Gate CI on ruff+mypy+pytest, not pytest alone.

## Summary

The biggest testing gap is missing lifecycle E2E coverage for lecture index usage. Addressing that plus unskipping ownership tests will substantially reduce regression risk.
