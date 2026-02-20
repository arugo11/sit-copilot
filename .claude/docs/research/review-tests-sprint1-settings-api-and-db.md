# Test Review: sprint1-settings-api-and-db

## Summary
- Current suite validates core happy paths and key validation behavior.
- Coverage is good for initial Sprint1 scope, with targeted gaps remaining.

## Findings

- [Medium] Missing API-level validation shape checks for additional invalid inputs
  - Files: `tests/api/v4/test_settings.py`
  - Currently validated: non-dict `settings` returns 400 with common error envelope.
  - Missing cases:
    - Missing `settings` field
    - Extra top-level fields
    - Malformed JSON payload
  - Recommendation: add 3 tests asserting consistent `{"error": ...}` 400 responses.

- [Low] Missing API test asserting `users` row creation side-effect
  - Files: `tests/api/v4/test_settings.py`
  - Service tests verify lazy creation of `users`, but API tests do not assert this integration behavior.
  - Recommendation: add one integration assertion that POST `/settings/me` creates both `users` and `user_settings`.

## Current Status
- `uv run pytest -q` passes for 15 tests.
- New tests cover schema, service, and API baseline behavior.
