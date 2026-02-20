# F0 Readiness Check Research & Constraints

**Feature**: `f0-readiness-check`  
**Date**: 2026-02-20  
**Research mode**: local evidence consolidation (Gemini research path blocked due missing `GEMINI_API_KEY`)

## 1. Project Brief (Draft)

Implement `POST /api/v4/course/readiness/check` as a deterministic backend endpoint that returns readiness guidance from syllabus-focused inputs within 5 seconds, with complete response fields even when optional inputs are missing.

## 2. Source Evidence

- Product/API contract: `docs/SPEC.md` (F0 section + API section + non-functional latency)
- Existing architecture patterns: `app/main.py`, `app/api/v4/procedure.py`, `app/schemas/procedure.py`, `app/services/procedure_qa_service.py`
- Error and test conventions: `app/core/errors.py`, `tests/conftest.py`, `tests/api/v4/test_procedure.py`

## 3. Functional Requirements (from SPEC)

- Endpoint: `POST /api/v4/course/readiness/check`
- Required response fields:
  - `readiness_score` (0-100)
  - `terms`
  - `difficult_points`
  - `recommended_settings`
  - `prep_tasks`
  - `disclaimer`
- Input should support:
  - required: `course_name`, syllabus content, `lang_mode`
  - optional: first material reference, self-level fields
- Processing constraints:
  - rule-based scoring is authoritative
  - LLM must not decide numeric score
  - response should be returned even with partial/insufficient optional input

## 4. Non-Functional Constraints

- Latency target: F0 response <= 5 seconds
- Determinism: same input should produce same score and core recommendations
- Backward-compatible error handling: use existing 400/401 contract

## 5. Design Decisions for Planning Baseline

1. **Deterministic-only MVP for scoring and generation**
- No external LLM call in F0 baseline.
- Benefit: deterministic behavior, no external dependency latency, easier testing.

2. **Heuristic extraction from syllabus text**
- Use lightweight keyword/regex heuristics for:
  - difficulty signals
  - term candidates
  - prep task suggestions
- Benefit: stable runtime and easy traceability of score components.

3. **Auth alignment with existing feature endpoints**
- Apply token guard using `X-Lecture-Token` for `/course/readiness/check`.
- Benefit: consistent API protection baseline with current lecture/settings flows.

4. **No persistence in F0 minimal**
- Return computed response directly; do not persist DB artifacts yet.
- Benefit: keeps scope bounded and avoids schema migration risk.

## 6. Scoring Heuristic Baseline (for implementation)

Proposed rule buckets (each bounded and additive):

- Text complexity signal (length, symbol density, prerequisite indicators)
- Domain difficulty signal (keywords indicating math/theory/report intensity)
- User self-level adjustment (`jp_level_self`, `domain_level_self`)
- Material-provided adjustment (`first_material_blob_path` presence only in baseline)

Score normalization:

- compute raw score
- clamp to `[0, 100]`
- map to recommendation intensity bands

## 7. Open Risks and Mitigations

- Risk: heuristic quality may be noisy for mixed Japanese/English text.
  - Mitigation: define explicit keyword dictionaries and deterministic fallback lists.
- Risk: optional file path is not equivalent to parsed PDF content.
  - Mitigation: treat path presence as minor weak signal in F0; defer PDF parsing to later phase.
- Risk: overfitting to one syllabus style.
  - Mitigation: unit tests with multiple syllabus fixtures and boundary cases.

## 8. Explicit Assumptions

- `syllabus_text` is provided as plain text in this phase.
- `first_material_blob_path` is accepted but not dereferenced to blob/PDF content in this phase.
- Endpoint can return informative defaults when text is short or sparse.
