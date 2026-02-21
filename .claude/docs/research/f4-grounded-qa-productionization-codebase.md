# F4 Grounded QA Productionization - Codebase Analysis

Generated: 2026-02-21  
Feature: `f4-grounded-qa-productionization`

## Analysis Method

- `context-loader` baseline: `.claude/rules/*`, `.claude/docs/DESIGN.md`
- Local repository analysis with `rg`, targeted file reads, and quality gate runs
- Gemini CLI status: unavailable in this environment for this task (`GEMINI_API_KEY` not set), so analysis is local-only fallback

## 1. Current System Snapshot

### API Endpoints (F4)

- `POST /api/v4/lecture/qa/index/build` (`app/api/v4/lecture_qa.py`)
- `POST /api/v4/lecture/qa/ask` (`app/api/v4/lecture_qa.py`)
- `POST /api/v4/lecture/qa/followup` (`app/api/v4/lecture_qa.py`)

### Service Pipeline

- Orchestration: `SqlAlchemyLectureQAService` (`app/services/lecture_qa_service.py`)
- Retrieval:
  - BM25 in-process store (`BM25LectureRetrievalService`)
  - Azure Search adapter (`AzureSearchLectureRetrievalService`)
- Index build:
  - BM25 index from `SpeechEvent` (`BM25LectureIndexService`)
  - Azure Search indexing from `LectureChunk`/`SpeechEvent` (`AzureLectureIndexService`)
- Answer generation: `AzureOpenAILectureAnswererService` (currently placeholder runtime call)
- Verification: `AzureOpenAILectureVerifierService` (currently placeholder runtime call)
- Follow-up rewrite: `SqlAlchemyLectureFollowupService` (LLM branch currently placeholder)

### Persistence

- `qa_turns` stores question/answer/confidence/citations/source IDs/latency (`app/models/qa_turn.py`)
- `lecture_sessions.qa_index_built` tracks index lifecycle readiness
- `lecture_chunks.indexed_to_search` tracks Azure indexing state per chunk

## 2. Contract and Spec Fit

### Grounded Contract Already Present

- Response includes `answer`, `confidence`, `sources`, `action_next`, optional `fallback`
- Deterministic no-source fallback exists in `lecture_qa_service`
- Source evidence includes chunk ID and timing metadata (`LectureSource`)

### Spec Drift to Acknowledge

- SPEC F4 examples emphasize `citations`, `answer_scope`, `suggested_followups`
- Current API contract exposes `sources` and does not currently return those exact fields
- Productionization plan should explicitly choose:
  - maintain current contract and harden internals first, or
  - include contract migration with compatibility policy

## 3. Strengths

- Thin API + DI boundaries are already in place (`app/api/v4/lecture_qa.py`)
- Retrieval/answer/verify/followup responsibilities are separated by service interfaces
- Session ownership check exists in orchestration before QA execution
- Azure Search service is process-shared and session-filtered
- Test suite baseline is healthy and broad

## 4. Productionization Gaps

## High

1. LLM runtime paths are still placeholders
- `lecture_answerer_service.py` and `lecture_verifier_service.py` return synthetic outputs
- `lecture_followup_service.py` LLM path is incomplete

2. Verification persistence semantics are optimistic
- `qa_turns.verifier_supported` is always set to `True`, even on fallback/no-source/verifier-fail paths
- This weakens auditability for groundedness SLIs

3. BM25 durability is process-local
- BM25 indexes are in-memory only
- Multi-worker/process restart behavior can drop index availability for BM25 path

## Medium

1. Observability is limited for groundedness control points
- No explicit reason codes for fallback/no-source/verifier-fail persistence
- No explicit QA metrics surface for citation integrity and verifier outcomes

2. Contract safety checks can be stronger
- No explicit guard that every citation/source maps to retrieved context IDs at response build time
- No explicit fail-closed policy tests for verifier parse failure in integration flow

## 5. Quality Baseline (Measured)

Executed on 2026-02-21:

- `uv run pytest -q` -> pass (`197 passed`)
- `uv run ruff check app tests` -> pass
- `uv run ty check app` -> pass
- Coverage reported by pytest-cov: `87%` total

This baseline is strong enough to add productionization work behind strict regression gates.

## 6. Recommended Scope for Productionization

### Include

- Real Azure OpenAI implementation for answer/verify/followup with strict timeout/error handling
- Deterministic fail-closed verifier behavior and explicit confidence downgrade policy
- Retrieval/index lifecycle hardening (BM25 fallback durability policy + Azure-primary runtime rules)
- Persistence audit upgrades (reason codes + accurate verifier support outcome)
- Grounded QA observability (latency/fallback/verifier/citation integrity metrics)
- End-to-end and failure-path tests for groundedness guarantees

### Exclude (for this feature)

- Frontend UX redesign
- Cross-feature auth redesign (e.g., replacing header-based identity with JWT) unless explicitly requested
- Large relevance-model overhaul beyond current BM25/Azure Search interface

