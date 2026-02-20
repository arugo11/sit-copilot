# Testing Review: f1-summary-and-finalize

Date: 2026-02-20
Reviewer: Codex (`team-review`)
Scope: tests added/updated for summary/finalize

## Findings

### Medium

1. Missing auth/ownership negative API cases for newly added endpoints
- `tests/api/v4/test_lecture.py:511`-`tests/api/v4/test_lecture.py:594` covers summary success + unknown session, but not missing token/user-id (401) and not owner-mismatch path.
- `tests/api/v4/test_lecture.py:596`-`tests/api/v4/test_lecture.py:723` covers finalize success + idempotency, but not unknown session, invalid status, missing token/user-id, owner mismatch.
- Recommendation:
  - Add endpoint-level 401/404/409 matrix tests to prevent authz regression.

2. Known ownership-validation behavior in QA remains untested (skipped)
- `tests/api/v4/test_lecture_qa.py:371` has a skipped ownership test for index build.
- With shared retriever integration, this increases risk of unnoticed cross-tenant regressions.
- Recommendation:
  - Replace skip with active test after converting service `ValueError` to mapped 404/403 behavior.

### Low

1. No concurrent summary generation test
- New summary service behavior is sensitive to concurrent calls for same window.
- Recommendation: add async concurrency test to lock in race-safe behavior after fix.

## Pass Summary
- Core happy-path and idempotency coverage for the feature is present.
- Highest missing value is negative auth/ownership and concurrency coverage.
