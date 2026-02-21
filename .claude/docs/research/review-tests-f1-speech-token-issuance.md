# Test Review: f1-speech-token-issuance

Date: 2026-02-21
Reviewer: Codex (`/team-review`)

## Review Scope

- `tests/api/v4/test_auth.py`
- `tests/unit/services/test_speech_token_service.py`
- `tests/unit/schemas/test_speech_token_schemas.py`
- implementation branches in `app/api/v4/auth.py` and `app/services/speech_token_service.py`

## Findings

### [Medium] API tests bypass the real DI factory path

- Files:
  - `tests/api/v4/test_auth.py:32`
  - `app/api/v4/auth.py:24`
- Observation:
  - API tests always override `get_speech_token_service`, so the default factory path is not exercised.
  - Coverage output already indicates uncovered path in factory function.
- Impact:
  - Wiring regressions between settings and service construction may escape tests.
- Recommendation:
  - Add one integration test that uses the real `get_speech_token_service()` with monkeypatched settings + monkeypatched requester.

### [Low] Missing unit test for empty token response branch

- Files:
  - `app/services/speech_token_service.py:57`
  - `tests/unit/services/test_speech_token_service.py`
- Observation:
  - Service has explicit guard for empty STS response token, but there is no test asserting this branch.
- Impact:
  - Regression risk on a safety-critical validation branch.
- Recommendation:
  - Add a unit test where requester returns `""` and assert `SpeechTokenProviderError`.

## Positive Checks

- Core contract cases are covered:
  - schema validation (valid/blank/non-positive expiry)
  - service config failure
  - provider failure mapping
  - API success/401/503 behavior
- Full suite run is green (`190 passed`).

## Severity Summary

- Critical: 0
- High: 0
- Medium: 1
- Low: 1

## Resolution Status (2026-02-21)

- [x] [Medium] Real DI factory path coverage: fixed with integration test using real factory and monkeypatched requester (`tests/api/v4/test_auth.py`).
- [x] [Low] Empty-token branch coverage: fixed with unit test asserting `SpeechTokenProviderError` (`tests/unit/services/test_speech_token_service.py`).
