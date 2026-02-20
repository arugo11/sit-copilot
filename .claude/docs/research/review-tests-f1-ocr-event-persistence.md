# Test Review: f1-ocr-event-persistence

## Validation Run

- `uv run pytest tests/unit/schemas/test_lecture_schemas.py tests/unit/services/test_lecture_live_service.py tests/api/v4/test_lecture.py -q` -> pass (`32 passed`)
- `uv run pytest -v` -> pass (`116 passed, 1 skipped`)
- `uv run ty check app/` -> pass

## Findings

### [Medium] Missing cross-user authorization tests for visual event ingest path

- Evidence:
  - Speech path has cross-user test (`tests/unit/services/test_lecture_live_service.py:180`).
  - No equivalent test exists for `ingest_visual_event` in service tests (`tests/unit/services/test_lecture_live_service.py:215-370`).
  - API tests for visual endpoint do not include cross-user ownership case (`tests/api/v4/test_lecture.py:259-415`).
- Risk:
  - Ownership regressions in visual ingest path could slip through undetected.
- Recommendation:
  - Add service + API tests that create a session under `owner_a` and attempt visual ingest as `owner_b`, asserting `404`.

### [Low] Missing API test for absent `X-User-Id` on visual endpoint

- Evidence:
  - Visual endpoint tests include missing lecture token (`tests/api/v4/test_lecture.py:378`), but no missing user-id case.
- Risk:
  - Auth dependency wiring regressions for user context may not be caught for this endpoint.
- Recommendation:
  - Add `POST /api/v4/lecture/visual/event` test without `X-User-Id` and assert `401`.

### [Low] Missing contract test for oversized upload rejection

- Evidence:
  - Current tests cover empty file and MIME type checks, but no max-size rejection scenario.
- Risk:
  - If upload size limits are introduced (recommended in security pass), behavior may regress without tests.
- Recommendation:
  - Add API test that uploads payload larger than configured max size and asserts deterministic `400` error contract.

## Positive Notes

- New visual ingest tests validate happy path, unknown session, inactive session, missing token, and invalid MIME type.
- Service tests validate OCR-failure fallback persistence (`quality=bad`) behavior.
- Schema tests cover core validation for content type and empty file payload.
