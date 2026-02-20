# Sprint2 Procedure QA Minimal Codebase Analysis

## Executive Summary

The current backend already has a stable FastAPI + SQLAlchemy async foundation and a proven TDD structure.  
`procedure-qa-minimal` can be implemented by extending the existing `api -> service -> model` pattern used in Sprint1.

Gemini CLI was detected but unavailable in this environment due missing `GEMINI_API_KEY`, so this analysis is based on local repository inspection.

## Current Architecture Snapshot

- App bootstrap and router registration are centralized in `app/main.py`.
- Versioned API modules live under `app/api/v4/`.
- Business logic uses service classes and protocol-style interfaces (`app/services/settings_service.py`).
- Database access is SQLAlchemy async with request-scoped auto-commit (`app/db/session.py`).
- ORM models are split by entity and loaded through `app/models/__init__.py`.
- API errors are normalized through shared handlers (`app/core/errors.py`).

## Existing Reusable Patterns

### API Layer Pattern

- Router per feature (`health.py`, `settings.py`).
- `/api/v4` prefix applied in `app/main.py`.
- Request/response schemas are explicit Pydantic models.

### Service Layer Pattern

- Protocol-like interface + concrete implementation.
- Route handlers are thin and delegate business logic.

### Persistence Pattern

- Async SQLAlchemy models with typed mapped columns.
- Session lifecycle and commit/rollback are handled by dependency injection.

### Testing Pattern

- Async integration tests with `httpx.AsyncClient` and `ASGITransport`.
- In-memory SQLite fixture and dependency override in `tests/conftest.py`.
- Unit tests validate schemas and service behavior.

## Gaps for Sprint2

- No procedure API endpoint exists.
- No retrieval/answerer interfaces exist for procedure QA.
- No `qa_turns` ORM model exists yet.
- No persistence path for procedure QA conversations.
- No rootless-answer guardrail (fallback when no evidence) exists for procedure QA.

## Proposed Placement for Sprint2 Files

- `app/api/v4/procedure.py`
- `app/schemas/procedure.py`
- `app/models/qa_turn.py`
- `app/services/procedure_retrieval_service.py`
- `app/services/procedure_answerer_service.py`
- `app/services/procedure_qa_service.py`
- `tests/api/v4/test_procedure.py`
- `tests/unit/services/test_procedure_qa_service.py`
- `tests/unit/schemas/test_procedure_schemas.py`

## Fit Assessment

The feature is a direct fit for existing architecture with low integration risk:

- Route wiring pattern already established.
- DB model/table creation is already automatic at startup.
- Test harness already supports API + DB integration.
- Error handling contract for validation is already in place.

