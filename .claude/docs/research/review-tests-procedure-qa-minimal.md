# Test Coverage Review: procedure-qa-minimal

## Scope

- `tests/api/v4/test_procedure.py`
- `tests/unit/services/test_procedure_qa_service.py`
- `tests/unit/schemas/test_procedure_schemas.py`
- Related implementation in `app/schemas/procedure.py` and `app/services/procedure_qa_service.py`

## Current State

- Targeted suite executed: `uv run pytest -q tests/api/v4/test_procedure.py tests/unit/services/test_procedure_qa_service.py tests/unit/schemas/test_procedure_schemas.py`
- Result: 9 passed.

## Findings

### Medium

1. Missing validation test for unsupported `lang_mode`.
   - Evidence: `lang_mode` is constrained by `Literal` in `app/schemas/procedure.py:28`, but no API/schema test asserts rejection for invalid values.
   - Risk: Contract regressions may go unnoticed if field is later widened accidentally.
   - Recommendation: Add API and schema tests for invalid `lang_mode` (expect 400 / ValidationError).

2. Persistence assertions do not verify full stored metadata.
   - Evidence: service tests verify `retrieved_chunk_ids_json` (`tests/unit/services/test_procedure_qa_service.py:83`, `tests/unit/services/test_procedure_qa_service.py:118`) but do not assert `citations_json`, `latency_ms`, and fallback-path `verifier_supported`.
   - Risk: Silent regressions in observability/audit fields.
   - Recommendation: Add assertions for stored `citations_json`, non-negative `latency_ms`, and `verifier_supported is False` in both branches.

### Low

1. Boundary behavior for query content is under-tested.
   - Evidence: tests cover missing field and normal values, but not whitespace-only query or oversized query.
   - Risk: UX inconsistency and potential storage abuse if query normalization changes.
   - Recommendation: Add schema/API cases for whitespace-only and max-length constraints once introduced.

## Summary

- Critical: 0
- High: 0
- Medium: 2
- Low: 1

