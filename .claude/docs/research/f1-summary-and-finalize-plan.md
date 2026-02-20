# F1 Summary + Finalize Implementation Plan

Generated: 2026-02-20  
Feature: `f1-summary-and-finalize`

## Objective

Implement SPEC step-5/6 backend flow:
- `GET /api/v4/lecture/summary/latest`
- `POST /api/v4/lecture/session/finalize`
- persistence for `summary_windows` and `lecture_chunks`
- idempotent finalize with stats response

## Architecture Plan

### Summary Latest Flow

1. Client calls `GET /api/v4/lecture/summary/latest?session_id=...`.
2. API authenticates `X-Lecture-Token` + `X-User-Id`.
3. Service validates session ownership.
4. Service computes latest 30-second window from latest event timestamp.
5. Service collects source events from recent 60-second lookback.
6. Service generates deterministic summary + key terms + evidence refs.
7. Service upserts `summary_windows` and returns payload.

### Finalize Flow

1. Client calls `POST /api/v4/lecture/session/finalize`.
2. API authenticates and validates session ownership.
3. Service checks session status:
   - `active`: run finalize pipeline
   - `finalized`: run idempotent return path
4. Pipeline builds/refreshes summary windows and lecture chunks.
5. Optional: if `build_qa_index=true`, trigger existing BM25 index builder.
6. Mark session finalized (`status=finalized`, `ended_at` set).
7. Return response with artifact stats.

## Module Boundaries

- `app/api/v4/lecture.py`
  - add `/summary/latest`
  - add `/session/finalize`
- `app/schemas/lecture.py`
  - add summary response schemas
  - add finalize request/response schemas
- `app/models/summary_window.py` (new)
- `app/models/lecture_chunk.py` (new)
- `app/services/lecture_summary_service.py` (new)
- `app/services/lecture_finalize_service.py` (new)
- update exports/wiring:
  - `app/models/__init__.py`
  - `app/services/__init__.py`
  - `app/main.py`
  - `tests/conftest.py`

## Data Model Tasks

### `summary_windows`

- fields:
  - `id`
  - `session_id` (FK + index)
  - `start_ms`, `end_ms`
  - `summary_text`
  - `key_terms_json`
  - `evidence_event_ids_json`
  - `created_at`

### `lecture_chunks`

- fields:
  - `id`
  - `session_id` (FK + index)
  - `chunk_type` (`speech|visual|merged`)
  - `start_ms`, `end_ms`
  - `speech_text`, `visual_text`, `summary_text`
  - `keywords_json`
  - `embedding_text`
  - `indexed_to_search` (default false)
  - `created_at`

## TDD Task Breakdown

1. Add failing schema tests (`tests/unit/schemas/test_lecture_schemas.py`)
- summary response contract
- finalize request/response contract
- invalid finalize payload cases

2. Add failing service tests for summary (`tests/unit/services/test_lecture_summary_service.py`)
- latest window generation from speech-only events
- mixed speech/visual evidence tag generation
- no-event fallback window behavior
- upsert (no duplicate window) behavior

3. Add failing service tests for finalize (`tests/unit/services/test_lecture_finalize_service.py`)
- active session finalize success
- repeated finalize idempotency
- unknown/other-user session handling
- optional `build_qa_index` path success/failure handling

4. Add failing API tests (`tests/api/v4/test_lecture.py`)
- `GET /lecture/summary/latest` success
- summary auth failure (401)
- summary unknown session (404)
- `POST /lecture/session/finalize` success
- finalize idempotent re-call
- finalize auth failure / state mismatch paths

5. Implement new ORM models + relationships.

6. Implement summary service (window selection, source aggregation, summary synthesis, upsert persistence).

7. Implement finalize service (artifact generation orchestration + session transition + stats).

8. Implement API routes and DI wiring in lecture router.

9. Update exports in `__init__` modules and metadata wiring in `main.py` / `tests/conftest.py`.

10. Run targeted quality gates and fix regressions.

## Dependency Graph

- Tasks 1-4 can be authored first in parallel (failing tests).
- Task 5 is prerequisite for service/API tests to pass.
- Task 6 is prerequisite for summary API.
- Task 7 depends on Task 6 and existing lecture index service integration.
- Task 8 depends on Tasks 6-7 and schema definitions.
- Task 9 follows model/service additions.
- Task 10 runs last.

## Verification Commands

- `uv run pytest tests/unit/schemas/test_lecture_schemas.py -q`
- `uv run pytest tests/unit/services/test_lecture_summary_service.py tests/unit/services/test_lecture_finalize_service.py -q`
- `uv run pytest tests/api/v4/test_lecture.py -q`
- `uv run ty check app/`
- `uv run ruff check app tests`

## Risks and Mitigations

1. Risk: finalize generates duplicate windows/chunks on retry
- Mitigation: deterministic upsert keys and explicit idempotency tests

2. Risk: long-session finalize latency
- Mitigation: O(n) passes, no nested scans, and worker-offload TODO note for next phase

3. Risk: route/service bloat in lecture module
- Mitigation: keep summary/finalize in dedicated services and thin API adapters

4. Risk: contract drift from SPEC response shape
- Mitigation: lock response schemas first via failing API/schema tests

## Scope Guard for `/team-implement`

Include only:
- summary/latest endpoint
- session/finalize endpoint
- `summary_windows` and `lecture_chunks` persistence
- idempotent finalize behavior
- tests for above

Do not include:
- Azure AI Search push
- frontend polling/UI changes
- real Azure OpenAI summarizer runtime

## Approval Gate

If approved, proceed to:
- `/team-implement f1-summary-and-finalize`
with the scope guard above fixed for this sprint.
