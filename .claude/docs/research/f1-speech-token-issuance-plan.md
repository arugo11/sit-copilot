# F1 Speech Token Issuance Implementation Plan

Generated: 2026-02-20  
Feature: `f1-speech-token-issuance`

## Objective

Implement SPEC section 10.3 by adding:
- `GET /api/v4/auth/speech-token`
- secure backend token exchange with Azure Speech STS
- stable response contract for frontend Speech SDK bootstrap

## Architecture Plan

### Request Flow

1. Client calls `GET /api/v4/auth/speech-token`.
2. API validates auth guard (`X-Lecture-Token`).
3. Route delegates to `SpeechTokenService`.
4. Service validates required settings (`azure_speech_key`, `azure_speech_region`).
5. Service calls Azure STS issue-token endpoint.
6. Service returns `{token, region, expires_in_sec}`.
7. Route maps service-level failures to HTTP-safe errors.

## Module Boundaries

- `app/api/v4/auth.py` (new)
  - route definition + DI for token service
- `app/schemas/speech_token.py` (new)
  - `SpeechTokenResponse`
- `app/services/speech_token_service.py` (new)
  - `SpeechTokenService` protocol
  - `AzureSpeechTokenService` implementation
  - typed domain errors for config/upstream failure
- update wiring:
  - `app/core/config.py` (speech settings)
  - `app/api/v4/__init__.py`
  - `app/main.py`
  - `app/services/__init__.py`
  - `app/schemas/__init__.py`

## API Contract Lock

### Endpoint

- `GET /api/v4/auth/speech-token`

### Success Response (200)

```json
{
  "token": "string",
  "region": "japaneast",
  "expires_in_sec": 540
}
```

### Error Mapping

- `401`: missing/invalid lecture token
- `503`: speech service temporarily unavailable or speech settings missing

## TDD Task Breakdown

1. Add failing schema tests
- `tests/unit/schemas/test_speech_token_schemas.py`
- response validation and bounds checks

2. Add failing service tests
- `tests/unit/services/test_speech_token_service.py`
- config-missing failure
- upstream non-200 failure
- success with mocked STS call

3. Add failing API tests
- `tests/api/v4/test_auth.py`
- success path
- missing auth header -> `401`
- upstream failure -> `503`

4. Implement settings + schema + service
- add speech config fields
- implement STS call and strict failure handling

5. Implement route + DI wiring
- add router file and register in app

6. Run quality gates and fix regressions

## Dependency Graph

- Tasks 1-3 first (failing tests)
- Task 4 before route pass conditions
- Task 5 after service contract stabilizes
- Task 6 last

## Verification Commands

- `uv run pytest tests/unit/schemas/test_speech_token_schemas.py -q`
- `uv run pytest tests/unit/services/test_speech_token_service.py -q`
- `uv run pytest tests/api/v4/test_auth.py -q`
- `uv run ty check app/`
- `uv run ruff check app tests`

## Risks and Mitigations

1. Risk: secret leakage through logs/errors
- Owner: Backend API implementer
- Mitigation: do not include key/token in exceptions or logs

2. Risk: response contract drift from SPEC
- Owner: Backend API implementer
- Mitigation: lock response schema and integration test first

3. Risk: token-expiry race in clients
- Owner: Frontend integrator + Backend API implementer
- Mitigation: return conservative `expires_in_sec=540` and document refresh guidance

4. Risk: tight coupling to one STS host format
- Owner: Backend API implementer
- Mitigation: construct endpoint from region with single utility and unit-test host generation

## Merge Gate

### Scope Freeze

- **Include**
  - backend `GET /api/v4/auth/speech-token`
  - Azure STS exchange service
  - speech settings wiring + tests
- **Exclude**
  - frontend SDK integration
  - token cache optimization
  - Entra ID migration

### Acceptance Criteria

- endpoint returns token payload with `token`, `region`, `expires_in_sec`
- invalid/missing lecture auth returns `401`
- Azure STS/config failures return `503`
- targeted tests pass for schema/service/API layers

### Key Risks and Mitigations

- secret leakage risk -> owner: Backend API implementer; sanitize error/log paths
- upstream dependency instability -> owner: Backend API implementer; deterministic error mapping and test coverage
- contract mismatch risk -> owner: Backend API implementer; contract-first tests before implementation

### Unresolved Questions

- None for implementation start. Defaults are locked as:
  - `X-Lecture-Token` only
  - per-request STS call (no cache)
  - fixed `expires_in_sec=540`
