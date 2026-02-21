# F4 Grounded QA Productionization - Implementation Plan

Date: 2026-02-21  
Feature: `f4-grounded-qa-productionization`

## 1. Objective

Harden F4 lecture QA into a production-ready grounded service by enforcing deterministic fallback, fail-closed verification, durable retrieval/index behavior, and auditable persistence without breaking current API consumers.

## 2. Scope Freeze

### Include

- Real Azure OpenAI runtime integration for:
  - answer generation
  - verifier
  - follow-up rewrite
- Grounded pipeline hardening for `/api/v4/lecture/qa/index/build`, `/ask`, `/followup`
- Deterministic no-source + verifier-fail safety behavior
- Citation/source integrity validation
- Persistence audit improvements (outcome reason + verifier outcome truthfulness)
- Groundedness observability and regression tests

### Exclude

- Frontend changes
- Broad auth migration (JWT/session redesign)
- Ranking model overhaul beyond current BM25 + Azure Search adapter boundaries
- Cross-feature API redesign outside lecture QA

## 3. Interfaces Locked

External API endpoints remain:

- `POST /api/v4/lecture/qa/index/build`
- `POST /api/v4/lecture/qa/ask`
- `POST /api/v4/lecture/qa/followup`

Current response contract remains backward-compatible:

- Keep existing fields (`answer`, `confidence`, `sources`, `action_next`, `fallback`, `verification_summary`, `resolved_query`)
- If new metadata is added, make it additive and optional only

Internal boundaries remain:

- `LectureRetrievalService`
- `LectureAnswererService`
- `LectureVerifierService`
- `LectureFollowupService`
- `LectureQAService`

## 4. Target Pipeline (Ordered Steps)

1. Validate session ownership + request
2. Retrieve sources (BM25 or Azure Search) with session scoping
3. If no sources: return deterministic low-confidence fallback and persist reason `no_source`
4. Generate draft answer from evidence-only prompt
5. Verify claims against retrieved sources
6. If verify fails: attempt one repair, then re-verify
7. If still unverifiable or verifier error: fail-closed fallback and persist reason
8. Return grounded response with citation/source integrity checks
9. Persist QA turn with outcome metadata and latency

## 5. Policy Statements

### Fallback Policy

- `sources == []` always returns deterministic low-confidence fallback.
- No-source outcomes are always persisted with explicit reason code.

### Verification Policy

- Verifier parse/runtime failures are fail-closed.
- High confidence is never returned when verification cannot be trusted.
- Repair path is single-attempt and must pass re-verification.

## 6. Task Breakdown

1. Real Azure OpenAI integration
- Files:
  - `app/services/lecture_answerer_service.py`
  - `app/services/lecture_verifier_service.py`
  - `app/services/lecture_followup_service.py`
- Work:
  - Implement actual async client call path
  - Add timeout + safe exception mapping
  - Keep deterministic fallback path for dependency failures

2. Orchestration hardening and audit semantics
- Files:
  - `app/services/lecture_qa_service.py`
  - `app/models/qa_turn.py`
  - `app/schemas/lecture_qa.py` (if additive fields are needed)
- Work:
  - Add explicit outcome reason codes (`no_source`, `verifier_fail`, `verifier_error`, `success`)
  - Persist truthful verifier support flag and reason
  - Enforce citation/source ID integrity checks before response

3. Retrieval/index lifecycle hardening
- Files:
  - `app/services/lecture_index_service.py`
  - `app/services/lecture_retrieval_service.py`
  - `app/api/v4/lecture_qa.py`
- Work:
  - Keep Azure-first retrieval when configured
  - Keep BM25 as controlled fallback with documented durability limits
  - Harden rebuild/skip behavior and error mapping consistency

4. Observability and operations
- Files:
  - `app/services/lecture_qa_service.py`
  - optional shared logging/metrics utility module
- Work:
  - Add structured logs and counters for fallback/verifier outcomes/latency
  - Ensure no secret leakage in logs/errors

5. Test expansion (mandatory)
- API tests:
  - index-build -> ask E2E with real lifecycle assertion
  - no-source deterministic fallback
  - verifier/runtime failure mapping
  - auth/ownership guard paths
- Service tests:
  - verifier fail-closed behavior
  - repair then re-verify behavior
  - citation integrity validation
  - persistence reason-code coverage

## 7. Dependency Order

1. Task 1 (runtime integrations)
2. Task 2 (orchestration semantics)
3. Task 3 (lifecycle hardening)
4. Task 4 (observability)
5. Task 5 (full regression tests + acceptance validation)

## 8. Verification Commands (Quality Gates)

- `uv run ruff check app tests`
- `uv run ruff format --check app tests`
- `uv run ty check app`
- `uv run pytest tests/unit/services/test_lecture_qa_service.py tests/unit/services/test_lecture_retrieval_service.py tests/api/v4/test_lecture_qa.py -q`
- `uv run pytest -q`

## 9. Risks and Mitigations

1. Risk: Azure OpenAI failure modes create unstable QA behavior
- Owner: QA runtime lane
- Mitigation: timeout/retry policy + fail-closed verification + deterministic fallback

2. Risk: Citation integrity drift between retrieval and response mapping
- Owner: QA orchestration lane
- Mitigation: explicit integrity validator + unit/API assertions

3. Risk: BM25 fallback misused as durable production primary
- Owner: retrieval/index lane
- Mitigation: Azure-first deployment policy + documented fallback intent + tests

4. Risk: Observability blind spots hide hallucination regressions
- Owner: quality/reliability lane
- Mitigation: add groundedness counters and SLI-aligned logs

## 10. Grounded QA Test Matrix

| Scenario | Expected Result | Test Layer |
|----------|-----------------|-----------|
| index build -> ask with matching content | grounded answer with non-empty sources | API E2E |
| ask without index/sources | deterministic low-confidence fallback | API + service |
| verifier parse/runtime error | fail-closed response (no high confidence) | service |
| verifier detects unsupported claims + repair success | repaired answer + downgraded confidence | service |
| citation/source mismatch | response blocked/fallback + logged reason | service |
| unauthorized/cross-user access | 401/404 path with no leakage | API |

## 11. Merge Gate

### Scope include/exclude freeze

- Include and exclude are explicit in section 2 and treated as fixed for `/team-implement`.

### Acceptance criteria

- Deterministic no-source fallback enforced and persisted with reason code
- Verifier fail-closed behavior enforced for parse/runtime failure
- Citation/source integrity guard active
- Azure OpenAI runtime path implemented with safe failure handling
- API/service tests cover happy path + fallback + verifier failure + auth/ownership
- Quality commands in section 8 pass

### Key risks and mitigations

- Defined in section 9 with owners and concrete mitigations

### Unresolved questions

- None blocking for implementation kickoff under current scope freeze

### Merge Gate Checklist Status

- `Scope Frozen`: Ready
- `Evidence Ready`: Ready (local repository evidence + measured quality gates)
- `Interfaces Locked`: Ready
- `Quality Gates Defined`: Ready
- `Risks Accepted`: Ready

## 12. Approval Gate

If approved, proceed to:

- `/team-implement f4-grounded-qa-productionization`

with the scope and merge gate in this plan fixed as implementation constraints.

