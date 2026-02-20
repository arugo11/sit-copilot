# F0 Readiness Check Codebase Analysis

**Feature**: `f0-readiness-check`  
**Date**: 2026-02-20  
**Method**: Local repository analysis (Gemini CLI unavailable because `GEMINI_API_KEY` is not set)

## 1. Current Backend Shape

The backend is a FastAPI app with explicit API/Service/Schema separation:

- API routes: `app/api/v4/*`
- Schemas: `app/schemas/*`
- Services: `app/services/*`
- Shared error mapping: `app/core/errors.py`
- Auth dependencies: `app/core/auth.py`

Routers are registered in `app/main.py` and each feature module owns its dependency wiring.

## 2. Reusable Patterns for F0

## 2.1 Route + DI Pattern

Current features (`procedure`, `lecture`) use:

- `APIRouter(prefix=..., tags=[...], dependencies=[Depends(auth_guard)])`
- typed dependency providers for service composition
- thin endpoint handlers that delegate to service layer

This pattern can be copied for F0 with a dedicated router.

## 2.2 Schema Validation Pattern

Current schema style (`app/schemas/procedure.py`, `app/schemas/lecture.py`):

- `ConfigDict(extra="forbid")`
- strict `Field()` constraints
- trim/blank-reject validators
- explicit Literals for enums (e.g., `LangMode`)

F0 request/response contracts should follow the same model discipline.

## 2.3 Error Contract Pattern

`app/core/errors.py` already normalizes:

- validation errors -> 400 + `validation_error`
- auth failures -> 401 + `http_error`

F0 can rely on this shared behavior without new global error code.

## 2.4 Test Strategy Pattern

Existing tests split by level:

- API integration: `tests/api/v4/*`
- Unit tests: `tests/unit/services/*`, `tests/unit/schemas/*`
- `tests/conftest.py` provides in-memory SQLite and `async_client`

F0 can be added with the same structure and fixtures.

## 3. Gap Analysis vs SPEC

From `docs/SPEC.md`:

- endpoint required: `POST /api/v4/course/readiness/check`
- response fields are fixed: score, terms, difficult points, recommended settings, prep tasks, disclaimer
- processing must be rule-first and deterministic for score
- latency target: within 5s

Current gap:

- no readiness schema/router/service exists
- no readiness-specific config knobs exist in `app/core/config.py`
- no tests for readiness endpoint

## 4. Proposed Module Boundaries for F0

- API: `app/api/v4/readiness.py`
  - HTTP contract only
  - auth and DI wiring
- Schemas: `app/schemas/readiness.py`
  - request + response model definitions
- Service: `app/services/readiness_service.py`
  - deterministic rule-based scoring
  - term extraction and response assembly

No DB model changes are required for F0 minimal readiness check.

## 5. Proposed File Changes

## 5.1 Create

- `app/api/v4/readiness.py`
- `app/schemas/readiness.py`
- `app/services/readiness_service.py`
- `tests/api/v4/test_readiness.py`
- `tests/unit/schemas/test_readiness_schemas.py`
- `tests/unit/services/test_readiness_service.py`

## 5.2 Update

- `app/main.py` (router registration)
- `app/api/v4/__init__.py` (module export)
- `app/core/config.py` (F0 knobs: score bounds, list size bounds, default disclaimer text)
- `app/schemas/__init__.py` and `app/services/__init__.py` (exports, if maintained)

## 6. Design Constraints from Existing Codebase

- Keep route handlers thin and side-effect free beyond service call.
- Keep response deterministic for identical input (no stochastic generation).
- Keep optional fields tolerant; missing optional input must still return full response shape.
- Keep auth behavior consistent with existing token-guarded feature endpoints.

## 7. Implementation Readiness Notes

- Existing codebase already has required dependency stack (FastAPI + Pydantic v2 + pytest + async test harness).
- No new external service integration is required for initial F0 endpoint.
- Main risk is designing deterministic heuristics that still produce useful output quality.
