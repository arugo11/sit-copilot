# Sprint2 Procedure QA Minimal Implementation Plan

## Objective

Deliver a minimal but contract-safe Procedure QA backend flow that enforces evidence-grounded answers and persists each QA turn.

## Architecture

### Request Flow

1. `POST /api/v4/procedure/ask` receives validated request.
2. Procedure QA service calls retriever interface.
3. Rootless guard checks `sources`.
4. If `sources` exists:
   - call answerer interface
   - build normal response
5. If `sources` empty:
   - skip answerer
   - build fallback response
6. Persist QA turn to `qa_turns`.
7. Return response with required fields.

### Module Boundaries

- API:
  - `app/api/v4/procedure.py`
- Schemas:
  - `app/schemas/procedure.py`
- Models:
  - `app/models/qa_turn.py`
- Services:
  - `app/services/procedure_retrieval_service.py` (Protocol + Fake)
  - `app/services/procedure_answerer_service.py` (Protocol + Fake)
  - `app/services/procedure_qa_service.py` (orchestration + persistence)

## File Change Plan

- Create:
  - `app/api/v4/procedure.py`
  - `app/schemas/procedure.py`
  - `app/models/qa_turn.py`
  - `app/services/procedure_retrieval_service.py`
  - `app/services/procedure_answerer_service.py`
  - `app/services/procedure_qa_service.py`
  - `tests/api/v4/test_procedure.py`
  - `tests/unit/schemas/test_procedure_schemas.py`
  - `tests/unit/services/test_procedure_qa_service.py`
- Update:
  - `app/main.py` (router registration)
  - `app/models/__init__.py` (export `QATurn`)
  - `app/schemas/__init__.py` (export procedure schemas)
  - `app/services/__init__.py` (export services if needed)
  - `app/api/v4/__init__.py` (module export)

## TDD Task Breakdown

1. Add failing schema tests for procedure request/response/source models.
2. Implement `app/schemas/procedure.py` to satisfy schema tests.
3. Add failing model/service tests for `qa_turns` persistence and rootless guard.
4. Implement `QATurn` model and service interfaces (retriever/answerer + fakes).
5. Implement orchestration service:
   - retrieval
   - rootless prohibition
   - fallback generation
   - persistence for both success/fallback
6. Add failing API integration tests for:
   - evidence hit -> sources included
   - no evidence -> fallback response
   - required fields always present
7. Implement `POST /api/v4/procedure/ask`.
8. Register router and exports.
9. Run quality commands and stabilize tests.

## Test Cases (Minimum)

- API:
  - `POST /api/v4/procedure/ask` returns 200 and all required fields.
  - Known query returns non-empty `sources` and non-empty answer.
  - Unknown query returns empty `sources` and non-empty `fallback`.
  - Turn is persisted in `qa_turns` in both paths.
- Service:
  - Rootless branch does not invoke answerer.
  - Evidence branch invokes answerer with retrieved sources.
  - `feature` is always stored as `"procedure_qa"`.
- Schema:
  - Reject invalid payload shape.
  - Enforce required response/source fields.

## Success Criteria Traceability

- `pytest` green: covered by TDD suite and command checks.
- Evidence input -> sources attached: API integration test.
- No-evidence input -> fallback: API integration + service tests.
- Persist to `qa_turns`: DB assertions in API/service tests.

## Verification Commands

- `uv run pytest -q`
- `uv run ruff check .`
- `uv run mypy .`

## Risks

- SQLite JSON serialization mismatch for sources.
  - Mitigation: use JSON column and explicit serialization in tests.
- Implicit contract changes while swapping fakes to real providers later.
  - Mitigation: keep Protocol interfaces stable and test against interfaces.
- Latency measurement inconsistency.
  - Mitigation: compute `latency_ms` in orchestration service with a single monotonic timer.

## Approval Gate

If approved, proceed to `/team-implement` for Sprint2 using this plan and keep Azure integrations mocked/fake as requested.

