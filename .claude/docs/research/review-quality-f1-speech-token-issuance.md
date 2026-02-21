# Quality Review: f1-speech-token-issuance

Date: 2026-02-21
Reviewer: Codex (`/team-review`)

## Review Scope

- `app/api/v4/auth.py`
- `app/services/speech_token_service.py`
- `app/schemas/speech_token.py`
- wiring updates (`app/main.py`, `app/api/v4/__init__.py`, `app/services/__init__.py`, `app/schemas/__init__.py`)

## Findings

### [Low] Requester callable typing is too loose for static guarantees

- File: `app/services/speech_token_service.py:16`
- Observation:
  - `SpeechTokenRequester = Callable[..., str]` accepts any callable shape.
  - `issue_token()` relies on keyword arguments (`sts_endpoint`, `speech_key`, `timeout_seconds`) but this contract is not enforced by type system.
- Impact:
  - Refactor-time safety is weaker; signature mismatches can surface only at runtime.
- Recommendation:
  - Replace with a strict `Protocol` (or `Callable[[...], str]` equivalent) that defines keyword-only parameters.

### [Low] Operational knobs are hardcoded in service defaults

- File: `app/services/speech_token_service.py:13`
- Observation:
  - `DEFAULT_STS_TIMEOUT_SECONDS=5`, `DEFAULT_TOKEN_EXPIRES_IN_SEC=540` are not externally configurable via settings.
- Impact:
  - Runtime tuning requires code changes/redeploy, reducing operational flexibility.
- Recommendation:
  - Add optional settings fields and pass through in `get_speech_token_service()` when needed.

## Positive Checks

- Route remains thin and delegates issuance concerns to service layer.
- Single-responsibility boundaries are clear (`auth` route + `speech_token_service`).
- Response schema is explicit and constrained (`token`, `region`, `expires_in_sec`).

## Severity Summary

- Critical: 0
- High: 0
- Medium: 0
- Low: 2

## Resolution Status (2026-02-21)

- [x] [Low] Requester typing looseness: fixed by introducing strict `SpeechTokenRequester` protocol (`app/services/speech_token_service.py`).
- [x] [Low] Operational hardcoding concern: fixed by exposing TTL/timeout knobs in settings and wiring them through DI (`app/core/config.py`, `app/api/v4/auth.py`).
