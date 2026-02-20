# Sprint3 F1 Speech Events + Subtitle Display Codebase Analysis

## Executive Summary

The current repository is a backend-only FastAPI service with stable async SQLAlchemy persistence and test infrastructure.  
Sprint3 can be implemented by extending the existing `api -> service -> model` pattern introduced in Sprint1/2.

Gemini CLI binary is present, but repository analysis via Gemini could not run in this environment because `GEMINI_API_KEY` is not configured. This report is based on local code inspection.

## Current Architecture Snapshot

- App bootstrap, DB table creation, and router registration are centralized in `app/main.py`.
- API modules are versioned under `app/api/v4/`.
- Business logic follows service boundaries (`app/services/*`) with protocol-oriented seams where needed.
- Persistence uses SQLAlchemy async sessions with request-scoped commit/rollback (`app/db/session.py`).
- Error responses are normalized to a shared JSON contract (`app/core/errors.py`).
- Async integration tests use `httpx.AsyncClient` + `ASGITransport` with in-memory SQLite overrides (`tests/conftest.py`).

## Existing Reusable Patterns

### API Layer

- Feature-specific routers (for example `settings.py`, `procedure.py`).
- Lightweight route handlers that delegate to services.
- Consistent validation/error behavior via Pydantic + common exception handlers.

### Service Layer

- Protocol + concrete implementation pattern is already established in procedure flow.
- Deterministic orchestration and persistence logic are tested at service level before API wiring.

### Persistence Layer

- ORM models are split by entity and exported from `app/models/__init__.py`.
- `Base.metadata.create_all` in app lifespan enables MVP-friendly table bootstrapping.

### Test Strategy

- Integration tests validate endpoint behavior and DB side effects.
- Unit tests validate schema constraints and service orchestration rules.

## Gaps for Sprint3

- No lecture-session model exists (`lecture_sessions` table missing).
- No speech-event model exists (`speech_events` table missing).
- No lecture live API endpoints exist (`/api/v4/lecture/session/start`, `/api/v4/lecture/speech/chunk`).
- No lecture live service exists for session lifecycle + speech event ingestion.
- No F1 schemas exist for lecture start/speech chunk payloads.
- No tests currently cover F1 subtitle event persistence.
- Repository currently has no frontend implementation, so subtitle display must be represented as backend API contract for client rendering.

## Proposed Placement for Sprint3

- API:
  - `app/api/v4/lecture.py`
- Schemas:
  - `app/schemas/lecture.py`
- Models:
  - `app/models/lecture_session.py`
  - `app/models/speech_event.py`
- Services:
  - `app/services/lecture_live_service.py`
- Tests:
  - `tests/api/v4/test_lecture.py`
  - `tests/unit/schemas/test_lecture_schemas.py`
  - `tests/unit/services/test_lecture_live_service.py`
- Wiring updates:
  - `app/main.py`
  - `app/api/v4/__init__.py`
  - `app/models/__init__.py`
  - `app/services/__init__.py`

## Fit Assessment

Sprint3 has low-to-medium integration risk because:

- Core backend architecture is already ready for new feature slices.
- Existing TDD harness can validate persistence and API behavior quickly.
- Most risk comes from defining a clear subtitle-display contract in a backend-only repository and keeping scope limited to Step 3 of the SPEC implementation order.
