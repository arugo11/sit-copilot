# Quality Review: sprint3-f1-speech-events-and-subtitles

## Scope

- Diff-based discovery fallback used because `git diff --name-only` was empty.
- Focused review on Sprint3-delivered code:
  - `app/api/v4/lecture.py`
  - `app/services/lecture_live_service.py`
  - `app/schemas/lecture.py`
  - `app/models/lecture_session.py`
  - `app/models/speech_event.py`
  - `app/main.py`

## Findings

### [Medium] ROI validation checks length/non-negative only, not geometry correctness

- Evidence:
  - `app/schemas/lecture.py:36` validates ROI non-negative.
  - No check for `x1 < x2` and `y1 < y2`.
- Impact:
  - Invalid ROI shapes (for example inverted boxes) can be persisted and may break later OCR stages.
- Recommendation:
  - Add ROI geometry validation for both `slide_roi` and `board_roi`.

### [Low] Hardcoded default user context in lecture service limits maintainability

- Evidence:
  - `app/services/lecture_live_service.py:27` defines `DEFAULT_LECTURE_USER_ID = "demo_user"`.
  - `app/services/lecture_live_service.py:60` uses this default in constructor.
- Impact:
  - Makes migration to authenticated multi-user flow more invasive.
- Recommendation:
  - Inject user context from auth dependency and remove service-level hardcoded default.

### [Low] Session ID generation has no collision retry path

- Evidence:
  - `app/services/lecture_live_service.py:126` generates session ID with date + 6-hex suffix.
  - Insert path (`app/services/lecture_live_service.py:84`) has no retry on collision.
- Impact:
  - Extremely low-probability primary key collision can surface as runtime DB error.
- Recommendation:
  - Retry ID generation on `IntegrityError` for robustness.

## Positive Notes

- Architecture alignment is good: API layer stays thin and delegates to service layer.
- Type annotations are complete and service boundaries are clear.
- Error serialization hardening in `app/core/errors.py` prevents non-JSON objects from breaking responses.
