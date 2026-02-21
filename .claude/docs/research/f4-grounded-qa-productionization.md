# F4 Grounded QA Productionization - Research and Constraints

Generated: 2026-02-21  
Feature: `f4-grounded-qa-productionization`

## 1. Project Brief (Assumption-Based)

Because this `/startproject` request only provided the feature name, this brief freezes assumptions from existing SPEC + current implementation.

### Goal

Productionize F4 lecture QA so answers remain evidence-first under real runtime conditions: deterministic no-source fallback, citation integrity, verifier-enforced groundedness, and auditable persistence.

### Scope (Assumed)

- Include:
  - harden `/lecture/qa/index/build`, `/ask`, `/followup`
  - replace placeholder LLM calls with real Azure OpenAI integration
  - enforce fail-closed verification behavior
  - ensure retrieval/index lifecycle is stable in production topology
  - add observability and acceptance tests for groundedness
- Exclude:
  - frontend redesign
  - non-F4 feature expansion
  - large auth model migration unless explicitly requested

### Success Criteria (Assumed)

- No-source path is deterministic and always safe
- Verified citations always map to retrieved context IDs
- Verifier parse/runtime failures cannot return high-confidence grounded answers
- QA turn persistence is audit-ready (outcome + reason)
- Existing quality gates remain green

## 2. Evidence and Sources

Primary local evidence used:

- `docs/SPEC.md` (F4 source-only behavior, verifier expectations, latency/availability targets)
- `app/api/v4/lecture_qa.py`
- `app/services/lecture_qa_service.py`
- `app/services/lecture_index_service.py`
- `app/services/lecture_retrieval_service.py`
- `app/services/lecture_answerer_service.py`
- `app/services/lecture_verifier_service.py`
- `app/services/lecture_followup_service.py`
- `.claude/docs/research/review-quality-f4-lecture-qa.md`
- `.claude/docs/research/review-security-f4-lecture-qa.md`
- `.claude/docs/research/review-tests-f4-lecture-qa.md`

Execution evidence:

- `uv run pytest -q` -> `197 passed`
- `uv run ruff check app tests` -> pass
- `uv run ty check app` -> pass

## 3. Constraints

### Functional

- F4 must remain source-grounded first (`source-only` default)
- Session isolation is required for retrieval (`session_id` scope)
- Fallback must be explicit when evidence is absent

### Operational

- External dependencies are Azure OpenAI and Azure Search, so timeout/retry/error mapping must be explicit
- Current env in workspace includes generated Azure settings; secret handling must remain outside logs/responses

### Architectural

- API layer should stay thin with DI service boundaries
- QA flow remains staged: retrieve -> answer -> verify -> persist
- Persistence schema should remain backward-compatible where possible

## 4. Findings

1. Grounded pipeline structure exists but runtime fidelity is incomplete
- Placeholder implementations in answerer/verifier/followup block true production readiness.

2. Deterministic no-source fallback is already implemented
- This is a strong base and should remain a locked contract.

3. Retrieval has dual backend strategy, but BM25 durability is limited
- In-memory BM25 is acceptable for local/dev fallback but not a primary production durability layer.

4. Audit fidelity needs improvement
- `verifier_supported=True` is currently set unconditionally in persisted `qa_turns`.

5. Test baseline is strong, but groundedness-specific acceptance checks should be explicit
- Existing coverage is high, but production gates need focused checks for fail-closed verifier behavior and citation integrity mapping.

## 5. Recommended Controls

### Fallback Policy (Lock)

- If `sources == []`, return fixed low-confidence fallback response.
- Persist the turn with explicit reason code (e.g., `no_source`).

### Verification Policy (Lock)

- Verifier parse/runtime errors are fail-closed.
- Fail-closed path must downgrade confidence and return safe fallback or repaired answer only when re-verified.

### Citation Integrity Policy (Lock)

- Every returned source/citation must map to retrieved chunk IDs in that request.
- Persist both citation payload and chunk ID list atomically.

### Runtime Hardening

- Real Azure OpenAI client wiring with bounded timeout and safe error mapping
- Retry strategy bounded to idempotent stages only
- Structured logging for request ID/session ID/latency/outcome (without secrets)

### Observability

- Define metrics:
  - `qa_requests_total`
  - `qa_no_source_total`
  - `qa_verifier_failed_total`
  - `qa_repair_attempt_total`
  - `qa_latency_ms`
  - `qa_citation_integrity_fail_total`

## 6. Anti-Patterns to Avoid

- Returning confident answers when verifier output is unavailable/invalid
- Treating BM25 in-memory index as production durability source of truth
- Persisting QA outcomes without reason metadata
- Logging prompt payloads that may include sensitive text or keys

## 7. Acceptance Matrix (Planning Baseline)

| Gate | Check | Current | Target |
|------|-------|---------|--------|
| Fallback determinism | `sources == []` => fixed low-confidence fallback | Partial (implemented, reason code missing) | Pass |
| Citation integrity | citations/sources map to retrieved IDs | Partial (stored, not explicitly validated) | Pass |
| Verifier fail-closed | parse/runtime failure blocks confident output | Partial (service-level behavior exists, no strict acceptance matrix) | Pass |
| Persistence auditability | outcome + reason codes stored | Fail (no reason code) | Pass |
| Security baseline | no hardcoded secrets and safe errors | Partial (historical risk noted, needs enforced checks) | Pass |

## 8. Research Limitations

- Gemini-driven external research was requested by workflow but unavailable in this environment because `GEMINI_API_KEY` is not set.
- This artifact is grounded in local repository evidence and existing project research files.

