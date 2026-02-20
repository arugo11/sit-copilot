# Security Review - lecture-index-azure-search-integration

Date: 2026-02-20
Reviewer: Codex (`/team-review`)
Scope: current uncommitted diff + newly added files for Azure Search integration

## Summary

- Critical: 0
- High: 0
- Medium: 1
- Low: 1

## Findings

### Medium

1. Query path requires index-management capability
- File: `app/services/azure_search_service.py:114`
- Detail: `search_lecture_documents()` always calls `ensure_lecture_index()`, which uses `create_or_update_index(...)` (`app/services/azure_search_service.py:72`).
- Risk: If operationally a read-only/query key is used for QA retrieval, `/lecture/qa/ask` can fail due to unauthorized management operation, causing availability/security-boundary issues (read path unexpectedly needs write privileges).
- Recommendation:
  - Remove schema-management call from search path, or
  - Guard it behind an explicit admin-only flag and run schema sync only during index-build/finalize flows.

### Low

1. OData filter string is hand-built
- File: `app/services/azure_search_service.py:119`
- Detail: Session filter is interpolated into a string; single quote escaping is done, but this remains custom query-string composition.
- Risk: Future changes could accidentally widen injection surface if escaping rules drift.
- Recommendation:
  - Keep strict normalization on `session_id` and add regression tests for special characters.
  - Centralize filter-expression construction in one tested helper.

## Positive Checks

- No new hardcoded Azure secrets introduced in Python code.
- Session filter is applied in Azure retrieval (`session_id eq ...`) which supports data isolation intent.
