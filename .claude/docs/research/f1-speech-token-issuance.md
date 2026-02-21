# F1 Speech Token Issuance Research

Generated: 2026-02-20  
Feature: `f1-speech-token-issuance`

## Project Brief

- Feature goal: add backend-issued short-lived Speech token endpoint for Azure Speech SDK clients.
- Requested feature: `/startproject f1-speech-token-issuance`.
- Primary product contract: `docs/SPEC.md` section 10.3 (`GET /api/v4/auth/speech-token`).

## Assumed Scope (for approval)

### Include

- `GET /api/v4/auth/speech-token`
- server-side call to Azure Speech STS with subscription key
- response payload:
  - `token`
  - `region`
  - `expires_in_sec`
- auth guard to prevent unauthenticated token minting
- schema/service/API tests for success and failure paths

### Exclude

- frontend Speech SDK integration (`speechTokenClient.ts`, token refresh loop)
- WebSocket STT streaming implementation
- Entra ID auth migration for Speech SDK
- persistence/audit table for token issuance events

## Evidence Summary

### 1. Token issuance should be backend-mediated

SPEC and project security intent explicitly require backend short-lived token issuance to avoid exposing long-lived Speech keys on frontend.

### 2. Azure Speech STS token exchange contract

Official Azure authentication documentation states:
- request: `POST /sts/v1.0/issueToken`
- required header: `Ocp-Apim-Subscription-Key`
- endpoint host shape: `https://<region>.api.cognitive.microsoft.com/...`
- issued token validity: 10 minutes

### 3. Client-side token refresh requirement

Speech SDK docs for `SpeechConfig.fromAuthorizationToken(...)` state that:
- token must be refreshed before expiry
- updating `SpeechConfig` token alone does not update already-created recognizers/synthesizers

## Design Implications

1. **Security boundary**
- subscription key never leaves backend.
- endpoint should require existing lecture token auth baseline.

2. **Response TTL strategy**
- SPEC example uses `expires_in_sec=540`.
- Azure token lifetime is 600 seconds; returning 540 gives a refresh safety buffer.

3. **Failure semantics**
- Azure STS transport/upstream failure should map to deterministic API failure (`503`).
- Missing speech config should fail fast at service boundary.

4. **Settings contract update**
- add typed settings for `azure_speech_key` and `azure_speech_region`.
- retain `.env.azure.generated` as source of values.

## Proposed Success Criteria

- `/api/v4/auth/speech-token` returns `200` with non-empty token, configured region, and bounded expiry metadata.
- endpoint rejects missing/invalid auth (`401`).
- endpoint returns `503` when speech service call fails or required speech settings are absent.
- tests cover success, auth failure, config failure, and upstream failure.

## Default Decisions Locked for This Plan

1. Require `X-Lecture-Token` only (no `X-User-Id` requirement in this feature).
2. Always issue by STS call per request in MVP (no server cache in this scope).
3. Treat speech misconfiguration/upstream failures as `503` to keep retry-safe behavior.

## Risks and Mitigations

- Risk: accidental subscription key exposure in logs.
  - Mitigation: never log key/token body; sanitize error paths.
- Risk: high QPS causes unnecessary STS calls.
  - Mitigation: keep API boundary ready for optional cache layer; defer until measured need.
- Risk: frontend token-refresh misunderstanding causes runtime failures.
  - Mitigation: document refresh-before-expiry contract and recognizer token update requirement.

## Source Notes

Detailed library notes are saved in:
- `.claude/docs/libraries/azure-speech-token.md`
