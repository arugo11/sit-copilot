# Lecture Index Azure Search Integration - Codebase Analysis

Date: 2026-02-20
Feature: `lecture-index-azure-search-integration`
Method: Local repository analysis (Gemini CLI unavailable in this shell because `GEMINI_API_KEY` is not set)

## 1. Current State Summary

The backend already has:
- Lecture session lifecycle and finalize flow (`/api/v4/lecture/session/finalize`)
- SQLite persistence for lecture artifacts (`lecture_chunks` table)
- In-memory BM25 index build endpoint (`/api/v4/lecture/qa/index/build`)
- Lecture QA endpoints (`/ask`, `/followup`) that currently depend on BM25-only retrieval

The backend does **not** yet have:
- Azure AI Search settings in `Settings`
- Azure Search client/service implementation
- Push indexing from `lecture_chunks` to Azure Search
- Search-time retrieval from Azure Search
- Status updates for `lecture_chunks.indexed_to_search`

## 2. Existing Data Flow (Important)

1. `POST /api/v4/lecture/session/finalize`
2. `SqlAlchemyLectureFinalizeService.finalize()`
3. `_rebuild_chunks()` creates `lecture_chunks` rows from:
- finalized `speech_events`
- usable `visual_events`
- `summary_windows`
4. Each chunk is saved with `indexed_to_search=False`
5. Optional `build_qa_index=True` triggers `LectureIndexService.build_index()`
6. Current `BM25LectureIndexService` fetches speech events and builds process-local BM25 index only
7. `LectureSession.qa_index_built` is set based on BM25 build result

Implication: finalize currently marks QA index as built even though Azure Search indexing is not implemented.

## 3. Relevant Files and Responsibilities

- `app/api/v4/lecture.py`
  - finalize endpoint and DI wiring
- `app/api/v4/lecture_qa.py`
  - `/index/build`, `/ask`, `/followup`
- `app/services/lecture_finalize_service.py`
  - rebuilds artifacts and optionally triggers index build
- `app/services/lecture_index_service.py`
  - BM25 index builder interface + implementation
- `app/services/lecture_retrieval_service.py`
  - BM25 retrieval interface + implementation
- `app/models/lecture_chunk.py`
  - canonical persisted lecture index source (`indexed_to_search` flag already present)
- `app/models/lecture_session.py`
  - `qa_index_built` state
- `app/core/config.py`
  - currently has Azure OpenAI only; no Azure Search config
- `tests/unit/services/test_lecture_finalize_service.py`
  - finalize behavior and index build success/failure contract
- `tests/api/v4/test_lecture_qa.py`
  - BM25 index build and QA request behavior

## 4. Schema Readiness vs SPEC

`lecture_chunks` already has the core fields needed for Azure indexing:
- ids and session relation (`id`, `session_id`)
- type and time range (`chunk_type`, `start_ms`, `end_ms`)
- searchable text fields (`speech_text`, `visual_text`, `summary_text`)
- keywords (`keywords_json`)
- marker (`indexed_to_search`)

Additional derived fields needed for search documents:
- `course_name` from `lecture_sessions`
- `date` derived from `LectureSession.started_at` (or explicit date field)
- `lang` from `LectureSession.lang_mode`
- unified searchable text for vectorization (`embedding_text` already exists)

## 5. Gaps to Close for This Feature

1. Configuration gap
- Need `azure_search_enabled`, endpoint, key, and index name settings

2. Service gap
- Need dedicated Azure Search service for:
  - index schema management (idempotent create/update)
  - document upsert (batch upload / merge-or-upload)
  - session-filtered retrieval query

3. Indexing contract gap
- `LectureIndexService` currently implies BM25 build only.
- Need to support Azure push indexing and return consistent status semantics.

4. Data consistency gap
- `lecture_chunks.indexed_to_search` is never updated to true.
- Need post-index update and failure-safe behavior.

5. Retrieval strategy gap
- QA retrieval uses process-local BM25 and loses data across process restarts.
- SPEC requires searchable `lecture_index` in Azure AI Search after finalize.

6. Operational gap
- No retry strategy, chunk batching policy, or partial-failure handling for search indexing.

## 6. Integration Points (Low-Risk Path)

- Keep `LectureIndexService` protocol but add Azure-backed implementation.
- Keep current BM25 path as fallback for local/dev if Azure disabled.
- Add new service module (recommended):
  - `app/services/azure_search_service.py` (or lecture-specific split)
- Update finalize flow:
  - After chunk rebuild, call Azure indexing for that session
  - Update `indexed_to_search` flags in transaction-safe manner
- Update retrieval DI in `lecture_qa.py`:
  - choose Azure retrieval when enabled, fallback to BM25 when disabled

## 7. Testing Surface

Add/extend tests for:
- settings validation for Azure Search env vars
- index build success/failure mapping to `qa_index_built`
- `indexed_to_search` update correctness
- ownership + session filtering preserved
- Azure-disabled fallback path (BM25)
- Azure service adapter with mocked SDK client (no real cloud calls in tests)

## 8. Risks Found in Current Code

- Semantic mismatch: `qa_index_built=True` can happen without cloud index availability.
- Current BM25 index is in-memory and process-local.
- Tokenization (`lower().split()`) is weak for Japanese queries.
- Existing QA tests mostly assert response shape, not grounding quality or source ranking behavior.

## 9. Suggested Direction

Use `lecture_chunks` + `lecture_sessions` as canonical source for Azure AI Search documents, and make finalize the single synchronization point (rebuild -> push -> flag update). Keep BM25 fallback for local development and safe rollback.
