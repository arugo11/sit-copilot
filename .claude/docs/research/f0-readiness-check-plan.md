# F0 Readiness Check Implementation Plan

## Objective

Deliver `POST /api/v4/course/readiness/check` with deterministic readiness scoring and complete contract-safe response fields in <=5s for typical syllabus-sized input.

## Architecture

## Request Flow

1. API receives `ReadinessCheckRequest`.
2. FastAPI validation enforces shape and bounds.
3. `ReadinessService.check()` computes:
   - normalized input
   - deterministic score
   - terms
   - difficult points
   - recommended settings
   - prep tasks
4. API returns `ReadinessCheckResponse`.

## Module Boundaries

- API
  - `app/api/v4/readiness.py`
  - responsibility: auth, request/response wiring, service injection
- Schemas
  - `app/schemas/readiness.py`
  - responsibility: strict contract validation and response shape
- Service
  - `app/services/readiness_service.py`
  - responsibility: deterministic rule logic only

## Data and Persistence Strategy

- No DB persistence in this feature phase.
- Inputs are processed in-memory and response is returned immediately.

## Interface Contract (Locked)

- Method/path: `POST /api/v4/course/readiness/check`
- Auth: `X-Lecture-Token` required
- Request fields:
  - `course_name: str`
  - `syllabus_text: str`
  - `first_material_blob_path: str | None = None`
  - `lang_mode: "ja" | "easy-ja" | "en" = "ja"`
  - `jp_level_self: int | None = None` (1..5)
  - `domain_level_self: int | None = None` (1..5)
- Response fields:
  - `readiness_score: int` (0..100)
  - `terms: list[{term, explanation}]`
  - `difficult_points: list[str]`
  - `recommended_settings: list[str]`
  - `prep_tasks: list[str]`
  - `disclaimer: str`

## File Change Plan

## Create

- `app/api/v4/readiness.py`
- `app/schemas/readiness.py`
- `app/services/readiness_service.py`
- `tests/api/v4/test_readiness.py`
- `tests/unit/schemas/test_readiness_schemas.py`
- `tests/unit/services/test_readiness_service.py`

## Update

- `app/main.py`
- `app/api/v4/__init__.py`
- `app/core/config.py`
- `app/schemas/__init__.py` (if export list is maintained)
- `app/services/__init__.py` (if export list is maintained)

## TDD Task Breakdown

1. Add schema tests for request/response validation and bounds.
2. Implement `app/schemas/readiness.py` to satisfy schema tests.
3. Add service unit tests for:
   - deterministic score range
   - sparse-input fallback behavior
   - list output length bounds
   - self-level adjustment behavior
4. Implement `app/services/readiness_service.py`.
5. Add API integration tests for:
   - 200 response shape
   - 400 validation errors
   - 401 when auth token missing
   - deterministic behavior for same payload
6. Implement `app/api/v4/readiness.py` and DI wiring.
7. Register router and exports.
8. Run quality gates and stabilize.

## Acceptance Criteria

- `POST /api/v4/course/readiness/check` returns 200 with all required fields.
- `readiness_score` is always within 0..100 and deterministic for same input.
- Missing optional fields still return complete response.
- Invalid payloads return shared 400 validation error schema.
- Missing auth token returns 401.
- Tests and static checks pass.

## Quality Gates

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy .`
- `uv run pytest -q`

## Risks and Mitigations

- Risk: low-quality term extraction for noisy text.
  - Mitigation: keep deterministic candidate extraction + fallback term list.
- Risk: ambiguity in recommendation generation.
  - Mitigation: map score bands to fixed recommendation templates.
- Risk: latency drift with very large syllabus payloads.
  - Mitigation: cap processed text length and avoid expensive NLP dependencies.

## Merge Gate

## Scope Freeze

- Include:
  - readiness check endpoint
  - deterministic rule-based scoring
  - auth + schema + tests
- Exclude:
  - PDF/blob content parsing
  - external LLM/OpenAI calls
  - persistence/analytics table changes

## Acceptance Freeze

- Contract fields fixed as listed in Interface Contract.
- Endpoint path and auth header fixed for this phase.
- Response always includes non-empty disclaimer.

## Key Risks Accepted

- Heuristic quality is acceptable for MVP baseline (owner: backend, mitigation: deterministic templates + tests).
- Blob path is treated as weak signal only (owner: backend, mitigation: explicit exclusion in this scope).

## Unresolved Questions

- None blocking for implementation start.
- Enhancement candidate after F0 baseline: parse first material content from blob/PDF and incorporate term-frequency weighting.
