# Security Review: f1-summary-and-finalize

Date: 2026-02-20
Reviewer: Codex (`team-review`)
Scope: working tree changes for F1 summary/finalize + affected QA path

## Findings

### High

1. Cross-user data access risk in lecture QA retrieval path
- `app/api/v4/lecture_qa.py:52` uses a process-wide shared retriever instance.
- `app/services/lecture_qa_service.py:104` and `app/services/lecture_qa_service.py:208` retrieve by `session_id` only; `user_id` is accepted but not used for authorization.
- `app/services/lecture_followup_service.py:127` loads history by `session_id` only and explicitly does not filter by `user_id`.
- Impact: if an attacker learns/guesses another user's `session_id`, they can query indexed lecture content and potentially conversation context from another tenant.
- Recommendation:
  - Add mandatory ownership check (`lecture_sessions.id + user_id`) at the start of `ask` and `followup`.
  - Filter follow-up history by owner via join/ownership validation.
  - Namespace cache keys as `(user_id, session_id)` or embed owner metadata in index and verify before retrieve.

### Low

1. Exception stack traces are logged on index build failure
- `app/services/lecture_finalize_service.py:143` logs with `exc_info=True`.
- Current message does not include sensitive payload, so risk is low.
- Recommendation: keep as-is, but maintain log scrubbing policy in production.

## Pass Summary
- No hardcoded secrets detected in changed files.
- No SQL-string concatenation or injection pattern detected in changed files.
- Main security concern is authorization gap on retrieval path.
