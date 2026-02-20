# F1 OCR Event Persistence Codebase Analysis

Generated: 2026-02-20
Feature: `f1-ocr-event-persistence`

## Summary

This repository already has F1 step-3 foundations:
- lecture session lifecycle persistence
- finalized speech event persistence
- lecture auth and per-user ownership checks

The missing slice for this feature is F1 step-4 visual OCR event ingestion and persistence (`visual_events`) aligned with `docs/SPEC.md`.

Gemini CLI binary exists, but analysis via Gemini could not run because `GEMINI_API_KEY` is not set in this environment. This report is based on local repository analysis.

## Current Architecture Relevant to F1

### API Layer

- `app/api/v4/lecture.py`
  - `POST /api/v4/lecture/session/start`
  - `POST /api/v4/lecture/speech/chunk`
- Router enforces lecture auth (`X-Lecture-Token`) and user context (`X-User-Id`).
- Route handlers are thin and delegate to service methods.

### Service Layer

- `app/services/lecture_live_service.py`
  - protocol + SQLAlchemy implementation pattern already in place
  - ownership-aware session fetch (`session_id` + `user_id`)
  - status gate (`active` session required)
  - persist-and-flush write flow

### Data Layer

- `app/models/lecture_session.py`
- `app/models/speech_event.py`
- startup table creation via `Base.metadata.create_all` in `app/main.py`
- tests use in-memory SQLite with shared metadata setup (`tests/conftest.py`)

### Validation + Error Contract

- Request validation uses Pydantic v2 models in `app/schemas/lecture.py`.
- API error payloads are normalized by `app/core/errors.py`.
- Validation failures return `400` with `validation_error` payload.

### Existing Test Coverage

- API integration: `tests/api/v4/test_lecture.py`
- schema validation: `tests/unit/schemas/test_lecture_schemas.py`
- service logic: `tests/unit/services/test_lecture_live_service.py`

Pattern quality is high and directly reusable for OCR event persistence.

## Gap Analysis for F1 OCR Event Persistence

### Missing Domain Entities

- No `VisualEvent` ORM model.
- `LectureSession` has no relationship to visual events.
- No `visual_events` export in `app/models/__init__.py` and startup imports.

### Missing API Contract

- No `POST /api/v4/lecture/visual/event` endpoint.
- No multipart/form-data ingestion path for ROI image upload.
- No response schema for OCR event acknowledgement.

### Missing Service Contracts

- `LectureLiveService` has no `ingest_visual_event` operation.
- No OCR adapter abstraction (Azure Vision client protocol / implementation).
- No quality classification policy implementation (`good|warn|bad`).

### Missing Tests

- No API tests for multipart upload + persistence side effects.
- No schema tests for visual event fields.
- No service tests for OCR success/failure and fallback persistence behavior.

## Integration Points (Recommended)

### New/Updated Models

- New: `app/models/visual_event.py`
- Update: `app/models/lecture_session.py`
  - add `visual_events` relationship
- Update exports/imports:
  - `app/models/__init__.py`
  - `app/main.py`
  - `tests/conftest.py`

### API + Schema

- Update `app/api/v4/lecture.py`:
  - add `POST /lecture/visual/event` route
  - accept multipart fields (`session_id`, `timestamp_ms`, `source`, `change_score`, `image`)
- Extend `app/schemas/lecture.py`:
  - response schema for visual ingest
  - optional shared enum/type definitions for `source`, `quality`

### Service + OCR Adapter

- Update `app/services/lecture_live_service.py`:
  - add `ingest_visual_event`
- New adapter module recommended:
  - `app/services/vision_ocr_service.py` (protocol + implementation)
- DI wiring in `app/api/v4/lecture.py` should keep router thin.

### Tests

- API: extend `tests/api/v4/test_lecture.py`
- Service: extend `tests/unit/services/test_lecture_live_service.py`
- Schema: extend `tests/unit/schemas/test_lecture_schemas.py`

## Risk Assessment

1. Multipart validation drift
- Risk: inconsistent validation between form fields and domain model.
- Mitigation: normalize input in service command object and validate early.

2. OCR provider coupling
- Risk: hard dependency on external OCR makes tests flaky.
- Mitigation: introduce protocol + fake implementation for tests.

3. Privacy regression
- Risk: accidentally persisting raw image bytes by default.
- Mitigation: persist only OCR metadata initially (`blob_path=None` by default).

4. Session ownership bypass
- Risk: cross-user writes if session ownership checks are skipped.
- Mitigation: reuse existing ownership query path before write.

## Recommendation

Use the existing `lecture live` vertical slice pattern and implement OCR persistence as a first-class extension of the same boundary:
- `lecture router` (HTTP)
- `lecture_live_service` (business policy)
- `visual_event` model (persistence)
- OCR adapter protocol (infra boundary)

This minimizes architecture drift and keeps implementation/test style consistent with current codebase.
