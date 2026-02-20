# Testing Review - lecture-index-azure-search-integration

Date: 2026-02-20
Reviewer: Codex (`/team-review`)
Scope: current uncommitted diff + newly added files for Azure Search integration

## Summary

- Critical: 0
- High: 1
- Medium: 2
- Low: 0

## Findings

### High

1. No test guards the `source-plus-context` contract in Azure mode
- Files:
  - `app/services/lecture_retrieval_service.py:294`
  - `tests/unit/services/test_lecture_retrieval_service.py:90`
- Detail: Current tests validate mapping/top-k only; they do not verify context expansion semantics for Azure path.
- Risk: Contract regression can pass CI unnoticed.
- Recommendation:
  - Add unit tests asserting context expansion behavior for Azure retrieval when `mode="source-plus-context"`.
  - Add API-level regression test that compares source counts/flags between modes.

### Medium

1. API integration tests do not exercise Azure-index build path end-to-end
- Files:
  - `tests/api/v4/test_lecture_qa.py:18`
  - `tests/api/v4/test_lecture_qa.py:584`
- Detail: Added tests only verify DI switch helper; they do not validate `/api/v4/lecture/qa/index/build` and `/ask` behavior under Azure-enabled configuration with mocked Azure service.
- Risk: Real route wiring regressions can slip through.
- Recommendation:
  - Use dependency overrides for `get_azure_search_service()` and run endpoint-level tests with Azure enabled.

2. No failure-path API tests for Azure retrieval/indexing errors
- Files:
  - `app/services/lecture_index_service.py:356`
  - `app/services/azure_search_service.py:95`
- Detail: Partial index failures raise `RuntimeError`, but no API-level test asserts user-visible behavior (fallback/500/handled response).
- Risk: Error handling may be unstable in production incidents.
- Recommendation:
  - Add tests for Azure indexing failure and Azure query failure in `/index/build`, `/ask`, and finalize-triggered build flows.

## Positive Checks

- New unit tests for `AzureLectureIndexService` cover success, skip, partial-failure, and speech-event fallback.
- New unit tests for `AzureSearchLectureRetrievalService` cover mapping and top-k behavior.
