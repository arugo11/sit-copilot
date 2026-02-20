# Security Review: procedure-qa-minimal

## Scope

- `app/api/v4/procedure.py`
- `app/schemas/procedure.py`
- `app/services/procedure_qa_service.py`
- `app/services/procedure_retrieval_service.py`
- `app/services/procedure_answerer_service.py`
- `app/models/qa_turn.py`
- `tests/api/v4/test_procedure.py`
- `tests/unit/services/test_procedure_qa_service.py`
- `tests/unit/schemas/test_procedure_schemas.py`

## Findings

### Medium

1. Procedure endpoint has no authentication/authorization boundary.
   - Evidence: `app/api/v4/procedure.py:22` defines the handler with only DB dependency and no auth dependency.
   - Risk: Anonymous callers can hit the endpoint and persist arbitrary `qa_turns`, increasing abuse surface.
   - Recommendation: Add an auth dependency (even temporary demo token guard) before enabling external access.

2. Request payload size is not bounded for `query`.
   - Evidence: `app/schemas/procedure.py:27` uses only `min_length=1`.
   - Risk: Very large input can inflate DB storage (`qa_turns.question`) and increase processing cost.
   - Recommendation: Add `max_length` (for example 512 or 1000) and test the 400 path for oversized requests.

### Low

1. Sensitive field policy is implicit, not enforced by schema/domain guards.
   - Evidence: Raw query is persisted directly in `app/services/procedure_qa_service.py:112`.
   - Risk: If upstream starts sending personal data, it will be retained without masking policy.
   - Recommendation: Document retention/redaction policy for `question` and add guardrails if needed.

## Summary

- Critical: 0
- High: 0
- Medium: 2
- Low: 1

