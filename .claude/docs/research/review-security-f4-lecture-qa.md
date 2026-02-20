# Security Review: f4-lecture-qa

## Scope

- `HEAD` is not available in this repository (initial commit state), so diff discovery used fallback:
  - `git status --porcelain`
  - targeted review of `app/`, `tests/`, env files, and `pyproject.toml`
- Reviewed focus files:
  - `.env.azure.generated`
  - `.env`
  - `app/core/config.py`
  - `app/core/auth.py`
  - `app/api/v4/settings.py`
  - `app/api/v4/lecture.py`
  - `app/api/v4/lecture_qa.py`
  - `tests/api/v4/test_settings.py`

## Findings

### [Critical] Plaintext cloud credentials are present in workspace env file

- Evidence:
  - `.env.azure.generated:12`
  - `.env.azure.generated:15`
  - `.env.azure.generated:18`
  - `.env.azure.generated:21`
  - `.env.azure.generated:25`
  - `.env.azure.generated:28`
- Risk:
  - API keys/connection strings can be leaked through accidental commit, logs, backups, or screen sharing.
  - Potential direct compromise of Azure resources.
- Recommendation:
  - Revoke and rotate all exposed credentials immediately.
  - Replace values with placeholders in repository files.
  - Load secrets only from Key Vault/secure runtime env.

### [High] No ignore guard for secret/artifact files increases accidental commit risk

- Evidence:
  - No `.gitignore` found at repository root.
  - `git status --porcelain` currently includes `.env`, `.env.azure.generated`, `.coverage`.
  - Runtime caches exist under `app/__pycache__` and `tests/**/__pycache__`.
- Risk:
  - Secrets and local artifacts are likely to be committed in future changes.
- Recommendation:
  - Add `.gitignore` for `.env*`, coverage files, and Python cache/build artifacts.
  - Add a pre-commit secret scan (for example `gitleaks`).

### [High] Settings endpoints are effectively unauthenticated and globally shared

- Evidence:
  - `app/api/v4/settings.py:12` router has no auth dependency.
  - `app/api/v4/settings.py:14` hardcodes `DEMO_USER_ID = "demo_user"`.
  - `app/api/v4/settings.py:27` and `app/api/v4/settings.py:41` always operate on the demo user.
  - `tests/api/v4/test_settings.py:13` and `tests/api/v4/test_settings.py:36` call endpoints with no auth headers.
- Risk:
  - Any caller can read/write the same settings record.
  - Multi-user boundary does not exist for this API.
- Recommendation:
  - Require authenticated identity for `/settings/me`.
  - Resolve user from auth context, not a constant.

### [Medium] Lecture user identity is client-asserted via header and not cryptographically bound

- Evidence:
  - `app/core/auth.py:53` accepts `X-User-Id` as source of identity.
  - `app/core/auth.py:70` returns header value directly after trim.
  - `app/api/v4/lecture.py:32` and `app/api/v4/lecture_qa.py:125` consume this value for ownership decisions.
- Risk:
  - If lecture token leaks/shared use occurs, caller can impersonate other user IDs by changing header value.
- Recommendation:
  - Derive user identity from signed token/session/JWT claims.
  - Treat `X-User-Id` as informational only, not trust anchor.

### [Medium] Insecure default API tokens exist in code defaults

- Evidence:
  - `app/core/config.py:13`
  - `app/core/config.py:14`
- Risk:
  - Deployments missing environment configuration may run with predictable credentials.
- Recommendation:
  - Remove insecure defaults and fail fast when tokens are unset.

## Summary

Top security priorities are credential rotation/removal and enforcing real per-user authentication on settings and lecture flows.
