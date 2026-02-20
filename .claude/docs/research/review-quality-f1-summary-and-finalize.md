# Quality Review: f1-summary-and-finalize

Date: 2026-02-20
Reviewer: Codex (`team-review`)
Scope: working tree changes for summary/finalize implementation

## Findings

### Medium

1. Summary upsert is race-prone under concurrent polling
- `app/services/lecture_summary_service.py:260` does read-then-insert/update with a unique constraint on `(session_id, start_ms, end_ms)`.
- Under concurrent `GET /lecture/summary/latest` requests for the same window, both requests can read `None` and attempt insert; one will raise `IntegrityError` and currently bubbles to 500.
- Recommendation:
  - Use DB upsert (`INSERT ... ON CONFLICT DO UPDATE`) or catch `IntegrityError` and retry update path.
  - Add a concurrency test (two simultaneous requests for same window).

2. Finalize can regress `qa_index_built` on transient index failure
- `app/services/lecture_finalize_service.py:99` assigns `session.qa_index_built = await self._build_qa_index(session_id)`.
- `app/services/lecture_finalize_service.py:142` returns `False` on exceptions.
- If session already had `qa_index_built=True`, a transient rebuild error flips it to `False`, creating inconsistent state.
- Recommendation:
  - Preserve previous true state (`session.qa_index_built = session.qa_index_built or build_success`).
  - Track last build attempt separately if needed.

### Low

1. Global quality gate not green due pre-existing unrelated debt
- `uv run ruff check .` fails in `.claude/` hooks and one unrelated test file.
- `uv run ruff format --check .` fails on pre-existing files outside this feature.
- Recommendation: separate cleanup PR to restore repo-wide gate health.

## Pass Summary
- Architecture split (model/service/api/test) is coherent and maintainable.
- Type hints and service boundaries are generally consistent.
