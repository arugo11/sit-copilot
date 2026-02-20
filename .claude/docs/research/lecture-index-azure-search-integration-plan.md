# Lecture Index Azure Search Integration - Implementation Plan

Date: 2026-02-20
Feature: `lecture-index-azure-search-integration`

## 1. Objective

Integrate Azure AI Search into lecture indexing and retrieval so that lecture finalize produces cloud-searchable index data and lecture QA can retrieve session-scoped evidence from Azure Search (with safe BM25 fallback).

## 2. Scope

### Include

- Azure Search settings and DI wiring
- Azure Search index schema management for `lecture_index`
- Push indexing from finalized `lecture_chunks`
- `indexed_to_search` status updates for indexed chunks
- Azure retrieval adapter for lecture QA (`session_id` filtered)
- BM25 fallback path when Azure is disabled/unavailable
- Tests for indexing/retrieval status and fallback behavior

### Exclude

- Frontend changes
- Full semantic re-ranker pipeline beyond current QA orchestration
- Production-scale index alias migration automation (optional future enhancement)
- Non-lecture indexes (e.g., `procedure_index` deep refactor)

## 3. Architecture

### 3.1 Module Boundaries

- `app/core/config.py`
  - add Azure Search config fields
- `app/services/azure_search_service.py` (new)
  - index lifecycle + document upsert + query interface
- `app/services/lecture_index_service.py`
  - add Azure-backed index service implementation
- `app/services/lecture_retrieval_service.py`
  - add Azure-backed retrieval implementation conforming to protocol
- `app/api/v4/lecture.py`
  - DI updates for finalize-time index build
- `app/api/v4/lecture_qa.py`
  - DI selection: Azure retrieval when enabled, BM25 fallback otherwise
- `tests/*`
  - update/add unit + API tests

### 3.2 Runtime Flow (Target)

1. `finalize` rebuilds `lecture_chunks`
2. Azure index service ensures index schema exists
3. Session chunks are transformed and upserted to Azure Search
4. Successfully indexed chunk rows set `indexed_to_search=true`
5. `LectureSession.qa_index_built` set true only when index push succeeds
6. QA retrieval uses Azure Search when enabled; always applies `session_id` filter
7. If Azure is disabled or unavailable, BM25 path remains operational

## 4. Task Breakdown

1. Add configuration fields and validation
- `azure_search_enabled`
- `azure_search_endpoint`
- `azure_search_api_key`
- `azure_search_index_name` (default `lecture_index`)
- optional `azure_search_semantic_configuration`, `azure_search_use_vectors`

2. Add SDK dependency
- add `azure-search-documents` to `pyproject.toml`

3. Implement Azure Search service adapter
- async clients initialization
- `ensure_lecture_index()`
- `upsert_lecture_documents(documents)`
- `search_lecture_documents(...)`

4. Implement Azure-backed lecture index builder
- fetch `lecture_chunks` + `lecture_session`
- map DB rows to Azure documents
- upsert in batches
- update `indexed_to_search` flags for successful IDs
- return `LectureIndexBuildResponse`

5. Wire finalize flow to Azure index builder
- preserve existing exception handling contract in finalize

6. Implement Azure-backed retrieval service
- map Azure results to `LectureSource`
- preserve `top_k` and `source-plus-context` contract (if context expansion needed, do local expansion strategy)

7. DI wiring and fallback strategy
- Azure enabled -> Azure retrieval/index service
- Azure disabled -> existing BM25 service

8. Tests
- config parsing tests
- index build success/failure + flag updates
- retrieval with enforced `session_id` filter
- fallback path tests when Azure disabled
- API regression tests for `/lecture/qa/index/build`, `/ask`, `/followup`

9. Verification and docs sync
- run lint/type/test gates
- update DESIGN and research docs if interface changes

## 5. Dependencies and Order

- Task 1 and 2 first
- Task 3 before 4 and 6
- Task 4 before finalize integration verification
- Task 6 before QA API regression validation
- Task 8 after core implementation

## 6. Verification Commands

- `uv sync`
- `uv run ruff check app tests`
- `uv run ruff format --check app tests`
- `uv run mypy app`
- `uv run pytest tests/unit/services/test_lecture_finalize_service.py tests/api/v4/test_lecture_qa.py -q`
- `uv run pytest -q`

## 7. Risks and Mitigations

- Risk: cloud indexing partial failure
- Mitigation: inspect result items and mark `indexed_to_search` per chunk ID

- Risk: retrieval behavior drift from current API expectations
- Mitigation: keep `LectureRetrievalService` protocol stable and add adapter-level tests

- Risk: secret exposure in logs
- Mitigation: never log endpoint keys, avoid dumping full settings

- Risk: local/dev friction without Azure
- Mitigation: explicit BM25 fallback via config toggle

## 8. Merge Gate

### Scope Freeze

- Include: lecture Azure Search integration for indexing/retrieval + fallback
- Exclude: frontend, broad ranking redesign, cross-feature refactor

### Acceptance Criteria

- `POST /api/v4/lecture/session/finalize` can index to Azure when enabled
- `POST /api/v4/lecture/qa/index/build` returns success and meaningful `chunk_count`
- `lecture_chunks.indexed_to_search` reflects successful indexing
- `POST /api/v4/lecture/qa/ask` returns session-filtered sources from Azure when enabled
- Azure-disabled mode keeps existing BM25 behavior
- test suite and quality gates pass

### Interfaces Locked

- Keep existing external API payloads for:
  - `/api/v4/lecture/session/finalize`
  - `/api/v4/lecture/qa/index/build`
  - `/api/v4/lecture/qa/ask`
  - `/api/v4/lecture/qa/followup`
- Internal protocol stability:
  - `LectureIndexService.build_index(...)`
  - `LectureRetrievalService.retrieve(...)`

### Quality Gates Defined

- `uv run ruff check app tests`
- `uv run ruff format --check app tests`
- `uv run mypy app`
- `uv run pytest -q`

### High Risks and Owners

- Azure SDK integration correctness
- Owner: backend implementation lane
- Mitigation: adapter unit tests with mocked clients

- Data consistency (`indexed_to_search` vs `qa_index_built`)
- Owner: finalize/indexing lane
- Mitigation: transaction-aware update and regression tests

- Retrieval relevance and source mapping
- Owner: QA retrieval lane
- Mitigation: protocol-level tests + API contract regression tests

### Unresolved Questions

- lexical-only first vs hybrid vector in this sprint
- immediate cutover vs staged dual-read validation period
- index alias rollout now vs later
