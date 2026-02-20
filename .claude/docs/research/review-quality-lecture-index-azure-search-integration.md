# Quality Review - lecture-index-azure-search-integration

Date: 2026-02-20
Reviewer: Codex (`/team-review`)
Scope: current uncommitted diff + newly added files for Azure Search integration

## Summary

- Critical: 0
- High: 2
- Medium: 2
- Low: 1

## Findings

### High

1. `source-plus-context` behavior regressed in Azure retrieval path
- File: `app/services/lecture_retrieval_service.py:294`
- Detail: `AzureSearchLectureRetrievalService.retrieve()` explicitly ignores `mode` and `context_window` (`_ = (mode, context_window)`) and returns only top-k direct hits.
- Impact: Existing API contract and behavior for `source-plus-context` are not preserved, likely reducing answer quality and violating expected retrieval semantics.
- Recommendation:
  - Implement context expansion for Azure path (e.g., retrieve wider candidate window and expand by timeline neighbors), or
  - Explicitly reject unsupported mode at API layer until implemented.

2. Azure service instance is recreated per request, defeating index-ready caching
- Files:
  - `app/api/v4/lecture.py:92`
  - `app/api/v4/lecture_qa.py:63`
  - `app/services/azure_search_service.py:52`
- Detail: `get_azure_search_service()` returns a new `AzureAISearchService` each call; `_index_ready` cache is instance-local, so schema create/update can be retriggered repeatedly.
- Impact: Unnecessary management calls, latency/cost increase, and higher throttling/error risk.
- Recommendation:
  - Provide process-shared Azure service singleton (same pattern as BM25 shared retriever), or
  - Cache `SearchClient`/`SearchIndexClient` lifecycle and schema-ready state across requests.

### Medium

1. Skip decision uses generic `qa_index_built` flag without backend distinction
- File: `app/services/lecture_index_service.py:333`
- Detail: Azure build returns `skipped` when `qa_index_built=True` and `rebuild=False`, even if the previous build may have been BM25-only.
- Impact: Migration edge case where Azure index is actually absent but build is skipped.
- Recommendation:
  - Track index backend/version in state, or
  - Verify Azure document existence before skip.

2. Index schema management is coupled to search execution path
- File: `app/services/azure_search_service.py:114`
- Detail: Read path and write path are tightly coupled via `ensure_lecture_index()`.
- Impact: Harder operational separation and reduced maintainability.
- Recommendation:
  - Move schema ensure to index-build lifecycle only; keep retrieval path read-focused.

### Low

1. API docstrings still describe BM25-only behavior
- File: `app/api/v4/lecture_qa.py:157`
- Detail: `/index/build` docstring says “Build BM25 search index...” though Azure path now exists.
- Impact: Documentation drift and developer confusion.
- Recommendation: Update route/service docstrings to backend-agnostic wording.
