# F1 Summary + Finalize Codebase Analysis

Generated: 2026-02-20  
Feature: `f1-summary-and-finalize`

## Executive Summary

The current backend already supports F1 session start, finalized speech ingest, and visual OCR event ingest.  
For this feature, the main gap is step-5/6 of SPEC: summary generation and finalize orchestration.

Gemini CLI binary is available, but repository analysis via Gemini could not run because `GEMINI_API_KEY` is not configured.  
This report is based on local code inspection.

## Current Implementation Snapshot

- Lecture APIs currently implemented:
  - `POST /api/v4/lecture/session/start`
  - `POST /api/v4/lecture/speech/chunk`
  - `POST /api/v4/lecture/visual/event`
- Lecture QA APIs currently implemented:
  - `POST /api/v4/lecture/qa/index/build`
  - `POST /api/v4/lecture/qa/ask`
  - `POST /api/v4/lecture/qa/followup`
- Common foundations are already stable:
  - Request-scoped async DB session with auto-commit/rollback
  - Unified API error shape (`validation_error`, `http_error`, `internal_server_error`)
  - Auth guards (`X-Lecture-Token`, `X-User-Id`)

## Existing Reusable Components

### 1. Session and ownership policy

- `SqlAlchemyLectureLiveService` already validates:
  - session existence
  - per-user ownership
  - active-status requirement for live ingest
- This can be reused for finalize authorization.

### 2. Event persistence already in place

- Persisted entities:
  - `lecture_sessions`
  - `speech_events`
  - `visual_events`
- This provides enough source material to generate summary windows and lecture chunks.

### 3. Local QA index builder available

- `BM25LectureIndexService` builds local BM25 index from finalized `speech_events`.
- Finalize can optionally call this service when `build_qa_index=true`.

### 4. Test harness is ready

- Integration tests already cover lecture route auth, session lifecycle checks, and DB assertions.
- Unit test patterns for service and schema layers are established and reusable.

## Gaps for `f1-summary-and-finalize`

### Missing APIs

- `GET /api/v4/lecture/summary/latest?session_id=...`
- `POST /api/v4/lecture/session/finalize`

### Missing persistent models

- `summary_windows`
- `lecture_chunks`

### Missing business orchestration

- Summary-window generation policy (30s update, 60s lookback context)
- Finalize workflow (idempotent session close, note/chunk generation, optional QA index build)
- Finalize stats payload construction (`speech_events`, `visual_events`, `summary_windows`, `lecture_chunks`)

### Missing tests

- Schema tests for summary/finalize request-response contracts
- Service tests for summary generation and idempotent finalize behavior
- API integration tests for success, auth, ownership, invalid state, and re-finalize behavior

## Proposed Module Placement

- API:
  - `app/api/v4/lecture.py` (add summary/finalize routes)
- Schemas:
  - `app/schemas/lecture.py` (add summary and finalize contracts)
- Models:
  - `app/models/summary_window.py` (new)
  - `app/models/lecture_chunk.py` (new)
  - `app/models/lecture_session.py` (relationship additions)
- Services:
  - `app/services/lecture_summary_service.py` (new)
  - `app/services/lecture_finalize_service.py` (new)
  - `app/services/lecture_live_service.py` (optional minimal integration point only)
- Wiring:
  - `app/models/__init__.py`
  - `app/services/__init__.py`
  - `app/main.py`
  - `tests/conftest.py`

## Scope Boundary Recommendation

In this feature:
- Include: local DB summary/finalize pipeline and optional local BM25 index build flag wiring
- Exclude: Azure AI Search push and real OpenAI summarization runtime

This keeps step-5/6 focused while preserving a clean handoff to a future step-7 feature.
