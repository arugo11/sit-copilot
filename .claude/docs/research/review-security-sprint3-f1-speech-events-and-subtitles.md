# Security Review: sprint3-f1-speech-events-and-subtitles

## Scope

- Diff-based target discovery fallback:
  - `git diff --name-only` returned empty in this workspace state.
  - Review target was derived from Sprint3 implementation files in `DESIGN.md`.
- Reviewed files:
  - `app/api/v4/lecture.py`
  - `app/services/lecture_live_service.py`
  - `app/schemas/lecture.py`
  - `app/models/lecture_session.py`
  - `app/models/speech_event.py`
  - `tests/api/v4/test_lecture.py`

## Findings

### [High] Lecture write endpoints have no authentication/authorization guard

- Evidence:
  - `app/api/v4/lecture.py:22` defines router without auth dependencies.
  - `app/api/v4/lecture.py:32` and `app/api/v4/lecture.py:45` expose write endpoints.
- Risk:
  - Anonymous callers can create sessions and persist arbitrary speech text.
  - Increases abuse surface (data poisoning, storage growth, operational noise).
- Recommendation:
  - Add a lecture auth dependency (same pattern as procedure token auth).
  - Bind user identity to request context and reject unauthenticated writes.

### [Medium] Session ownership is not validated during speech ingestion

- Evidence:
  - `app/services/lecture_live_service.py:93` queries by `LectureSession.id` only.
  - `app/services/lecture_live_service.py:60` uses hardcoded user context default.
- Risk:
  - If session IDs are discovered, cross-session writes become possible in multi-user mode.
- Recommendation:
  - Pass authenticated `user_id` into service.
  - Query with both `session_id` and `user_id`, then reject mismatches.

## Notes

- No hardcoded secrets or sensitive logging were found in Sprint3 implementation files.
- Input validation is generally strong (timing/confidence/finality/consent constraints in schemas).
