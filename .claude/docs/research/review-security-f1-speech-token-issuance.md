# Security Review: f1-speech-token-issuance

Date: 2026-02-21
Reviewer: Codex (`/team-review`)

## Review Scope

- `app/api/v4/auth.py`
- `app/services/speech_token_service.py`
- `app/core/config.py`
- `tests/api/v4/test_auth.py`
- `tests/unit/services/test_speech_token_service.py`

## Findings

### [Medium] Token issuance endpoint has no abuse throttling/audit hook

- File: `app/api/v4/auth.py:17`
- Observation:
  - Endpoint requires `X-Lecture-Token`, but there is no request throttling or issuance audit guard in route/service boundary.
  - If lecture token leaks, attacker can mint short-lived speech tokens repeatedly until key rotation.
- Impact:
  - Increased operational and billing exposure under token abuse.
- Recommendation:
  - Add minimal server-side control (rate limiting per token/IP) and issuance telemetry (count + failure ratio).
  - Optional: require `X-User-Id` on this endpoint if per-user traceability is needed.

### [Low] `azure_speech_region` accepts arbitrary string without format validation

- File: `app/core/config.py:22`
- Observation:
  - Region is a free-form string; malformed value is only detected at runtime via network failure.
- Impact:
  - Misconfiguration causes avoidable runtime outages and harder diagnostics.
- Recommendation:
  - Add startup-level validation for region format (e.g., `^[a-z0-9-]+$`) and fail fast with clear config error.

## Positive Checks

- No hardcoded secret values found in changed source files.
- Error mapping avoids leaking key/token values (`503` with generic message).
- Subscription key remains backend-only; response payload returns short-lived token only.

## Severity Summary

- Critical: 0
- High: 0
- Medium: 1
- Low: 1

## Resolution Status (2026-02-21)

- [x] [Medium] Token issuance endpoint abuse control: fixed via in-memory rate limit + issuance telemetry (`app/api/v4/auth.py`).
- [x] [Low] `azure_speech_region` format validation: fixed via settings validator (`app/core/config.py`) and tests (`tests/unit/test_config.py`).
