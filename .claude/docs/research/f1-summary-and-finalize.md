# F1 Summary + Finalize Research

Generated: 2026-02-20  
Feature: `f1-summary-and-finalize`

## Project Brief

- Feature goal: implement F1 step-5/6 backend behavior for live summary and lecture session finalize.
- User request context: `/startproject f1-summary-and-finalize`.
- Primary source of truth: `docs/SPEC.md` (F1 API, data model, non-functional, acceptance criteria).

## Assumed Scope (for approval)

### Include

- `GET /api/v4/lecture/summary/latest?session_id=...`
- `POST /api/v4/lecture/session/finalize`
- Persistence for:
  - `summary_windows`
  - `lecture_chunks`
- Finalize response stats and idempotency
- Optional local QA index build trigger (`build_qa_index=true`) via existing BM25 service
- Full schema/service/API tests for the above

### Exclude

- Azure AI Search ingestion (`lecture_index` remote push)
- Real Azure OpenAI summary generation
- Frontend polling/UI implementation
- Worker queue offloading (keep synchronous finalize for MVP)

## Hard Constraints from SPEC

1. Summary cadence and evidence
- Update summary every 30 seconds.
- Use recent 60-second reference window.
- Attach required evidence tags: `speech|slide|board`.

2. Fallback behavior
- OCR quality degradation should not break lecture flow.
- Audio confidence degradation should allow summary pause/degrade behavior.

3. Finalize behavior
- Finalize must generate note/chunk outcomes for post-lecture QA preparation.
- Finalize should be idempotent and re-runnable for same session.

4. Data completion requirement
- `lecture_sessions`, `speech_events`, `visual_events`, `summary_windows`, `lecture_chunks`, `qa_turns` should be representable in DB lifecycle.

5. Privacy/safety
- No raw audio/video persistence by default.
- Session ownership/auth boundaries must remain enforced.

## Design Implications

### 1. Keep summarization deterministic in MVP

Because real LLM runtime is still placeholder in this repository, summary generation should be deterministic/rule-based first:
- aggregate latest finalized speech text
- blend high-quality visual OCR text (`good|warn`)
- derive key terms heuristically

This enables stable tests and predictable behavior.

### 2. Separate summary and finalize orchestration services

To keep single responsibility and avoid bloating `lecture_live_service`:
- `LectureSummaryService`: window computation and persistence
- `LectureFinalizeService`: session transition + batch summary/chunk build + optional QA index build

### 3. Finalize idempotency contract

Recommended behavior:
- First call on `active` session:
  - generate missing summary/chunk artifacts
  - mark session `finalized`
  - set `ended_at`
- Repeated call on `finalized` session:
  - return existing/updated stats without duplicating windows/chunks

### 4. Summary window keying policy

To avoid duplicates, use stable `(session_id, start_ms, end_ms)` semantics.
If a window exists, update text/terms/evidence instead of insert-duplicate.

### 5. Chunk generation policy for step-6

For MVP, create `lecture_chunks` from:
- finalized speech events (`chunk_type=speech`)
- visual OCR events (`chunk_type=visual`, quality-filtered)
- merged summary windows (`chunk_type=merged`)

Store local fields required by SPEC now, defer remote index push.

## Proposed Success Criteria

- Summary endpoint returns latest window payload with summary, key terms, evidence tags.
- Finalize endpoint is idempotent and returns stable stats.
- `summary_windows` and `lecture_chunks` rows are created and queryable.
- `build_qa_index=true` path can set `qa_index_built` using existing local BM25 builder.
- Ownership/auth and inactive-session edge cases remain safe.

## Open Questions (Approval Items)

1. Should `summary/latest` be callable for both `active` and `finalized` sessions, or only `active`?
2. For `build_qa_index=true`, should finalize fail hard when index build fails, or return partial success with `qa_index_built=false`?
3. Should `lecture_chunks` include low-quality visual OCR (`quality=bad`) as metadata-only entries, or skip them entirely?
4. Should summary generation prefer deterministic-only now, or allow optional Azure OpenAI path behind config flag in the same sprint?

## Risk Notes

- Risk: Scope expands into step-7 Azure Search too early.
  - Mitigation: explicitly defer remote indexing to dedicated next feature.
- Risk: finalize latency spike with long sessions.
  - Mitigation: keep algorithm linear, cap chunk generation per call if needed, and document worker migration path.
- Risk: duplicate artifacts on retry.
  - Mitigation: deterministic window/chunk upsert keys + finalize idempotency tests.
