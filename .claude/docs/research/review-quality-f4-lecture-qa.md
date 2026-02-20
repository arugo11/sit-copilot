# Quality Review: f4-lecture-qa

## Scope

- `HEAD` unavailable; review target derived from working tree (`git status --porcelain`) and implementation files.
- Main review areas:
  - lecture QA API/service/index/retrieval path
  - settings API behavior
  - lint/type-check status

## Validation Run

- `uv run pytest -q` -> pass (`102 passed, 1 skipped`)
- `uv run ruff check app tests` -> fail (`1` import-order error)
- `uv run mypy app tests` -> fail (`105` errors)

## Findings

### [High] Lecture index lifecycle is broken across requests due per-request in-memory service instantiation

- Evidence:
  - `app/api/v4/lecture_qa.py:50` returns a new `BM25LectureRetrievalService()` each dependency resolution.
  - `app/api/v4/lecture_qa.py:98` injects retrieval service into ask flow.
  - `app/services/lecture_retrieval_service.py:96` stores indexes only in instance memory (`self._indexes`).
  - Reproduction run in this review session:
    - `/api/v4/lecture/qa/index/build` returned `chunk_count: 1`
    - subsequent `/api/v4/lecture/qa/ask` returned fallback with `sources: []`.
- Impact:
  - Core feature behavior is incorrect: index build does not benefit later ask/follow-up requests.
- Recommendation:
  - Make retrieval/index storage process-wide singleton or persistent (DB/Redis/file cache).
  - Ensure build and ask use the same index store across requests.

### [High] Azure OpenAI integration path is stubbed and dependency wiring disables real QA behavior

- Evidence:
  - `app/api/v4/lecture_qa.py:57` and `app/api/v4/lecture_qa.py:66` pass empty credentials.
  - `app/services/lecture_answerer_service.py:158` TODO for real OpenAI call; `:165` returns fixed placeholder text.
  - `app/services/lecture_verifier_service.py:175` TODO for real verification call; `:187` always returns successful JSON.
- Impact:
  - QA/verification correctness is not production-ready and can misrepresent confidence/grounding.
- Recommendation:
  - Wire credentials from settings/env and implement actual OpenAI calls with robust error handling.
  - Mark endpoints as preview/disabled until real integration is complete.

### [Medium] Follow-up rewrite path is logically incorrect when OpenAI key exists

- Evidence:
  - `app/services/lecture_followup_service.py:232` TODO placeholder.
  - `app/services/lecture_followup_service.py:245` returns `self._simple_rewrite(prompt, "")` (uses prompt text as question).
- Impact:
  - If OpenAI path is enabled, rewrite output can be malformed and unrelated to intended question.
- Recommendation:
  - Implement `_call_openai_rewrite` correctly and add failure fallback returning original question.

### [Medium] Strict typing contract is currently broken

- Evidence:
  - `uv run mypy app tests` reports `105` errors.
  - Production code example: `app/services/lecture_qa_service.py:271` assigns `LectureAskResponse` into a follow-up response variable.
- Impact:
  - Type-level regressions can hide runtime issues and reduce maintainability.
- Recommendation:
  - Fix production typing issues first, then either clean up tests or relax test typing scope intentionally.

### [Low] Lint gate is not clean

- Evidence:
  - `uv run ruff check app tests` reports import ordering issue at `tests/unit/services/test_lecture_qa_service.py:3`.
- Impact:
  - Minor hygiene issue; indicates quality gate not fully enforced.
- Recommendation:
  - Run `uv run ruff check --fix .` and keep lint checks required in CI.

## Summary

Highest quality issue is the broken build->ask index lifecycle. Real OpenAI integration and typing health are the next priorities.
