# Security Review: f1-ocr-event-persistence

## Scope

- Diff-based discovery fallback used because `git diff --name-only` returned empty in this workspace state.
- Review target derived from feature implementation files:
  - `app/api/v4/lecture.py`
  - `app/schemas/lecture.py`
  - `app/services/lecture_live_service.py`
  - `app/services/vision_ocr_service.py`
  - `app/models/visual_event.py`
  - `tests/api/v4/test_lecture.py`
  - `tests/unit/services/test_lecture_live_service.py`

## Findings

### [High] Unbounded file read allows memory exhaustion via oversized uploads

- Evidence:
  - `app/api/v4/lecture.py:105` reads the entire uploaded file into memory (`await image.read()`).
  - `app/schemas/lecture.py:135` only validates `image_size > 0` (no upper bound).
- Risk:
  - Attackers can upload very large files and exhaust worker memory, causing degraded service or process crashes.
- Recommendation:
  - Add a maximum upload size (for example `MAX_VISUAL_IMAGE_BYTES`) and bounded read logic (`await image.read(limit + 1)` + reject on overflow).
  - Return structured `400 validation_error` when the limit is exceeded.

### [Medium] Image type validation trusts client-provided MIME type only

- Evidence:
  - `app/api/v4/lecture.py:106` relies on `image.content_type`.
  - `app/schemas/lecture.py:146-153` validates only MIME strings (`image/jpeg`, `image/jpg`).
- Risk:
  - A non-image payload can be labeled as JPEG and bypass validation. This becomes more dangerous when a real OCR/image parser is integrated.
- Recommendation:
  - Add server-side signature validation for JPEG bytes (magic bytes at minimum).
  - Prefer parsing validation in OCR adapter boundary before processing.

## Positive Notes

- AuthN/AuthZ guard is present at route level through `require_lecture_token` and `require_user_id` via dependency chain.
- Session ownership checks are enforced in service layer before persistence (`app/services/lecture_live_service.py:166-170`).
- No hardcoded secrets or sensitive logging were found in the reviewed feature files.
