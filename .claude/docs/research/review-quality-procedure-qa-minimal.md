# Quality Review: procedure-qa-minimal

## Scope

- `app/api/v4/procedure.py`
- `app/services/procedure_qa_service.py`
- `app/services/procedure_retrieval_service.py`
- `app/services/procedure_answerer_service.py`
- `app/models/qa_turn.py`
- `app/schemas/procedure.py`

## Findings

### Medium

1. Route is tightly coupled to fake implementations.
   - Evidence: `app/api/v4/procedure.py:27`-`app/api/v4/procedure.py:30` instantiate `FakeProcedureRetrievalService` and `FakeProcedureAnswererService` inside request handler.
   - Impact: Swapping to real Azure-backed services requires route edits instead of configuration/DI swap, increasing rollout risk.
   - Recommendation: Inject `ProcedureRetrievalService` and `ProcedureAnswererService` through FastAPI dependencies (factory/provider functions).

2. Configuration knobs are hardcoded in orchestration service.
   - Evidence: retrieval limit is fixed at `limit=3` in `app/services/procedure_qa_service.py:54`, fallback strings are constants in `app/services/procedure_qa_service.py:23`-`app/services/procedure_qa_service.py:24`.
   - Impact: Behavior cannot be tuned per environment/language without code changes.
   - Recommendation: Move these values into `app/core/config.py` (or explicit constructor params) and pass from dependency provider.

### Low

1. Naming mismatch may create future confusion (`sources` vs `citations_json`).
   - Evidence: response uses `sources` (`app/schemas/procedure.py:38`) while persistence stores the same payload in `citations_json` (`app/services/procedure_qa_service.py:115`).
   - Impact: Minor cognitive overhead when adding analytics or migrations.
   - Recommendation: Add code comment/mapping note in service/model clarifying this intentional cross-feature naming.

## Summary

- Critical: 0
- High: 0
- Medium: 2
- Low: 1

