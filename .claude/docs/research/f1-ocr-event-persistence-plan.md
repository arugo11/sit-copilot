# F1 OCR Event Persistence Implementation Plan

Generated: 2026-02-20
Feature: `f1-ocr-event-persistence`

## Objective

Implement F1 step-4 by adding OCR visual event ingestion and persistence while preserving existing lecture boundaries and fallback safety.

## Architecture Plan

### Request Flow

1. Client calls `POST /api/v4/lecture/visual/event` with multipart payload.
2. API validates basic form/file fields and delegates to lecture live service.
3. Service verifies session ownership and active status.
4. Service calls OCR adapter for text + confidence extraction.
5. Service derives `quality` and persists `visual_events` row.
6. API returns event acknowledgement with OCR metadata.

### Module Boundaries

- API: `app/api/v4/lecture.py`
- Schema types: `app/schemas/lecture.py`
- Service orchestration: `app/services/lecture_live_service.py`
- OCR adapter: `app/services/vision_ocr_service.py` (new)
- Persistence model: `app/models/visual_event.py` (new)

## Data Model Plan

Create `visual_events` with fields:
- `id` (uuid string)
- `session_id` (FK lecture_sessions.id, indexed)
- `timestamp_ms` (int)
- `source` (`slide|board`)
- `ocr_text` (text)
- `ocr_confidence` (float)
- `quality` (`good|warn|bad`)
- `change_score` (float)
- `blob_path` (nullable string)
- `created_at` (timezone-aware datetime)

Update `LectureSession` relationship:
- `visual_events: list[VisualEvent]`

## Delivery Tasks (TDD-first)

1. Add failing schema tests
- file: `tests/unit/schemas/test_lecture_schemas.py`
- target: visual event response typing / enum guard / numeric constraints

2. Add failing service tests
- file: `tests/unit/services/test_lecture_live_service.py`
- target:
  - success persistence of `visual_events`
  - unknown session `LectureSessionNotFoundError`
  - inactive session `LectureSessionInactiveError`
  - OCR failure fallback persists `quality=bad`

3. Add failing API integration tests
- file: `tests/api/v4/test_lecture.py`
- target:
  - successful multipart ingest + DB assertion
  - unknown session 404
  - inactive session 409
  - missing auth 401
  - invalid field/form payload 400

4. Implement persistence model + exports
- create `app/models/visual_event.py`
- update:
  - `app/models/lecture_session.py`
  - `app/models/__init__.py`
  - `app/main.py`
  - `tests/conftest.py`

5. Implement OCR adapter abstraction
- create `app/services/vision_ocr_service.py`
  - protocol interface
  - deterministic default implementation (MVP-safe)

6. Implement lecture service extension
- update `app/services/lecture_live_service.py`
  - add `ingest_visual_event`
  - integrate OCR adapter
  - quality derivation + fallback behavior

7. Implement API endpoint wiring
- update `app/api/v4/lecture.py`
  - new multipart route
  - DI provider for OCR adapter-aware service

8. Implement schemas
- update `app/schemas/lecture.py`
  - add visual response model and shared literals

9. Run quality gates
- `uv run pytest -q`
- `uv run ruff check app tests`
- `uv run mypy app tests`

## Dependency Graph

- Tasks 1-3 can start in parallel.
- Task 4 is prerequisite for DB assertions in Tasks 2-3 to pass.
- Task 5 precedes Task 6.
- Task 6 and Task 8 precede Task 7.
- Task 9 runs after all implementation tasks.

## Verification Checklist

- `visual_events` table is created at startup/tests metadata load.
- Event row includes expected session linkage and OCR metadata.
- Route behavior matches existing lecture error conventions.
- OCR failure path does not raise 500 and still persists fallback record.
- No raw image bytes are persisted to DB by default.

## Risks and Mitigations

1. OCR dependency blocks local tests
- Mitigation: protocol + deterministic default implementation

2. Multipart input validation bypasses Pydantic safeguards
- Mitigation: explicit form parsing + service-level normalization checks

3. Over-scope into storage and summarize features
- Mitigation: hard boundary to visual-event persistence only

4. Inconsistent quality classification across services
- Mitigation: centralize quality mapping in lecture live service

## Approval Gate

After approval, proceed to `/team-implement f1-ocr-event-persistence` with scope fixed to:
- visual OCR event ingest endpoint
- `visual_events` persistence
- fallback-safe OCR handling
- full schema/service/API tests
