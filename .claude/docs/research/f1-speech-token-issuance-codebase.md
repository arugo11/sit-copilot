# F1 Speech Token Issuance Codebase Analysis

Generated: 2026-02-20  
Feature: `f1-speech-token-issuance`

## Executive Summary

The backend currently has no auth-token endpoint for Azure Speech SDK.
`docs/SPEC.md` defines `GET /api/v4/auth/speech-token`, but `app/api/v4` has no `auth.py` route module and no speech-token service abstraction yet.

Gemini CLI binary exists on this machine, but repository analysis through Gemini is unavailable because `GEMINI_API_KEY` is not configured. This report is based on local code inspection.

## Current Implementation Snapshot

- Existing API groups:
  - `health`, `settings`, `procedure`, `lecture`, `lecture_qa`, `readiness`
- Existing auth guard patterns:
  - `X-Procedure-Token` for procedure APIs
  - `X-Lecture-Token` (+ optional `X-User-Id`) for lecture/readiness/settings APIs
- Common error envelope already standardized in `app/core/errors.py`.
- `.env.azure.generated` already contains `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`, but `app/core/config.py` currently does not expose speech-specific settings fields.

## Reusable Building Blocks

### 1. Thin router + service DI pattern

- Route modules mostly keep HTTP mapping thin.
- Business logic is delegated to service classes/protocols.
- This pattern fits speech token issuance well.

### 2. Centralized settings object

- `Settings` in `app/core/config.py` is already the single source for runtime config.
- `.env` + `.env.azure.generated` loading is already configured.

### 3. Unified error model

- Validation, HTTP exceptions, and unexpected failures are normalized.
- Speech-provider failures can map to predictable `503` while preserving the same response shape.

### 4. Existing integration-test style

- API tests use `httpx.AsyncClient` + in-memory SQLite fixture.
- Auth header conventions and negative-path tests are already established in `tests/api/v4/*`.

## Gaps for `f1-speech-token-issuance`

### Missing route and schema

- No `GET /api/v4/auth/speech-token` endpoint.
- No schema currently modeling `{token, region, expires_in_sec}` response.

### Missing service boundary

- No service dedicated to Azure Speech STS token exchange.
- No runtime HTTP client abstraction for speech token issuance in app code.

### Missing speech settings contract

- `Settings` lacks:
  - `azure_speech_key`
  - `azure_speech_region`
  - optional timeout/ttl knobs for token issuance behavior

### Missing tests

- No endpoint tests for:
  - success path
  - auth failure
  - misconfiguration (missing key/region)
  - upstream speech STS failure mapping

## Recommended Module Placement

- API:
  - `app/api/v4/auth.py` (new router)
- Schema:
  - `app/schemas/speech_token.py` (new response model)
- Service:
  - `app/services/speech_token_service.py` (new protocol + implementation)
- Wiring updates:
  - `app/api/v4/__init__.py`
  - `app/main.py`
  - `app/core/config.py`
  - `app/services/__init__.py`
  - `app/schemas/__init__.py`

## Scope Boundary Recommendation

In this feature:
- Include: backend token issuance endpoint and secure server-side exchange with Azure Speech STS.
- Exclude: frontend SDK wiring, token refresh loop implementation in browser, and Entra ID migration path.

This keeps the feature narrowly aligned with SPEC section 10.3 and unlocks frontend speech SDK integration without exposing the subscription key.
