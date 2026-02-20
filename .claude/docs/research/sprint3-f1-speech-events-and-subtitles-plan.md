# Sprint3 F1 Speech Events + Subtitle Display Implementation Plan

## Objective

Implement SPEC step 3 by adding lecture session start and speech event ingestion APIs with DB persistence, while keeping scope limited to audio-event storage and subtitle-display support contract.

## Architecture

### Request Flow

1. Client calls `POST /api/v4/lecture/session/start`.
2. API validates request and consent flag.
3. Lecture live service creates `lecture_sessions` row with `status="active"`.
4. Client sends finalized subtitle event to `POST /api/v4/lecture/speech/chunk`.
5. Service validates active session + timing/quality constraints.
6. Service persists `speech_events` row.
7. API returns ingestion acknowledgement for subtitle continuity.

### Module Boundaries

- API:
  - `app/api/v4/lecture.py`
- Schemas:
  - `app/schemas/lecture.py`
- Models:
  - `app/models/lecture_session.py`
  - `app/models/speech_event.py`
- Services:
  - `app/services/lecture_live_service.py`

## File Change Plan

- Create:
  - `app/api/v4/lecture.py`
  - `app/schemas/lecture.py`
  - `app/models/lecture_session.py`
  - `app/models/speech_event.py`
  - `app/services/lecture_live_service.py`
  - `tests/api/v4/test_lecture.py`
  - `tests/unit/schemas/test_lecture_schemas.py`
  - `tests/unit/services/test_lecture_live_service.py`
- Update:
  - `app/main.py` (lecture router registration + model import)
  - `app/api/v4/__init__.py` (lecture module export)
  - `app/models/__init__.py` (new model exports)
  - `app/services/__init__.py` (new service exports)
  - `app/core/config.py` (optional F1 limits/constants if needed)
  - `tests/conftest.py` (ensure metadata load includes new models)

## TDD Task Breakdown

1. Add failing schema tests for lecture start and speech chunk payload validation.
2. Implement `app/schemas/lecture.py` to satisfy validation tests.
3. Add failing service tests:
   - session creation persists `lecture_sessions`
   - speech ingestion persists `speech_events`
   - inactive/missing session is rejected
   - `is_final=False` is rejected
4. Implement ORM models (`LectureSession`, `SpeechEvent`) and service logic.
5. Add failing API integration tests for:
   - session start success
   - speech chunk success
   - consent missing/false rejection
   - invalid timing/confidence rejection
   - non-existent session rejection
   - DB side effects for both tables
6. Implement lecture API router and dependency wiring.
7. Register router + exports.
8. Run quality gates and fix issues.

## Test Cases (Minimum)

- API:
  - `POST /lecture/session/start` returns `200`, `session_id`, `status=active`.
  - `POST /lecture/session/start` with `consent_acknowledged=false` returns `400`.
  - `POST /lecture/speech/chunk` returns `200` acknowledgement and event identifier.
  - `POST /lecture/speech/chunk` rejects invalid ranges/values.
  - `POST /lecture/speech/chunk` rejects unknown or non-active sessions.
- Service:
  - Session row is created with expected defaults.
  - Speech event row is linked to session and stores normalized fields.
  - Only final events are accepted.
- Schema:
  - Enforce enum constraints (`lang_mode`, `speaker`).
  - Enforce numeric constraints (`start_ms`, `end_ms`, `confidence`).
  - Reject extra fields (`extra="forbid"`).

## Success Criteria Traceability

- "F1 音声イベント保存": verified by DB assertions on `speech_events`.
- "字幕表示": supported by successful ingestion acknowledgement contract for finalized subtitles.
- "Step 3 only": no OCR/summary/finalize implementation introduced.

## Verification Commands

- `uv run pytest -q`
- `uv run ruff check app tests`
- `uv run mypy .`

## Risks

- Risk: Session lifecycle complexity expands unexpectedly.
  - Mitigation: keep statuses minimal (`active|finalized|error`), implement only `active` creation in Sprint3.
- Risk: Endpoint contract drifts from SPEC examples.
  - Mitigation: align fields and enums directly with `docs/SPEC.md`.
- Risk: Subtitle-display interpretation mismatch.
  - Mitigation: freeze response acknowledgement contract and validate in API tests.

## Approval Gate

If approved, proceed to `/team-implement` for `sprint3-f1-speech-events-and-subtitles` with strict Sprint3 scope (session start + speech chunk only).
