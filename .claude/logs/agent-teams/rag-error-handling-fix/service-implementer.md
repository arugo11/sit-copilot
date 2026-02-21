# Service Implementer Work Log

## Task: Lecture QA Service Error Handling Fixes

### Date
2026-02-22

### Assigned Tasks
1. Add `_build_local_grounded_response()` helper method
2. Add `_safe_verify()` and `_safe_repair()` helper methods
3. Add `LectureAnswererError` handling in `ask()` method
4. Add `LectureAnswererError` handling in `followup()` method

### Changes Made to `app/services/lecture_qa_service.py`

#### 1. Imports Added
- `LectureAnswererError` from `lecture_answerer_service`
- `LectureVerifierError` from `lecture_verifier_service`
- Added `DEFAULT_BACKEND_FAILURE_FALLBACK` constant

#### 2. Constructor Modified
- Added `backend_failure_fallback` parameter with default value

#### 3. New Helper Method: `_build_local_grounded_response()`
Builds a local grounded response from sources when Azure OpenAI fails.
- Takes up to 2 source snippets (120 chars each)
- Returns Japanese response formatted with source excerpts
- Returns fallback message if no valid snippets

#### 4. New Helper Method: `_safe_verify()`
Safely wraps `verifier.verify()` to catch `LectureVerifierError`.
- Returns failed verification result on error
- Prevents 503 errors from propagating to API layer

#### 5. New Helper Method: `_safe_repair()`
Safely wraps `verifier.repair_answer()` to catch `LectureVerifierError`.
- Returns `None` on error (repair failed)
- Allows graceful degradation

#### 6. Modified `ask()` Method
- Wrapped `answerer.answer()` in try/except for `LectureAnswererError`
- Calls `_safe_verify()` instead of direct `verifier.verify()`
- Calls `_safe_repair()` instead of direct `verifier.repair_answer()`
- Returns local grounded response on answerer error

#### 7. Modified `followup()` Method
- Wrapped `answerer.answer()` in try/except for `LectureAnswererError`
- Calls `_safe_verify()` instead of direct `verifier.verify()`
- Calls `_safe_repair()` instead of direct `verifier.repair_answer()`
- Returns local grounded response wrapped in `LectureFollowupResponse` on error

### Verification
- [x] `uv run ruff check .` passes
- [x] `uv run ty check app/` passes

### Pattern Reference
Implementation follows the exact pattern from `procedure_qa_service.py`:
- Error handling for `ProcedureAnswererError` → `LectureAnswererError`
- Local grounded response builder with source excerpts
- Safe verifier wrapper methods

### Key Design Decisions
1. **Local fallback preserves sources**: Even when Azure OpenAI fails, sources are returned to the user
2. **200-level response on backend failure**: API returns success with fallback message instead of 503 error
3. **Verifier error = failed verification**: Safe fallback treats verifier errors as verification failures
4. **Repair error = no repair**: Safe repair returns None, continuing with original draft

### Files Modified
- `app/services/lecture_qa_service.py`: All error handling changes

### Status
**All tasks completed successfully.**
