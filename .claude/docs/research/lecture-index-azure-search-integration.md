# Lecture Index Azure Search Integration - Research and Constraints

Date: 2026-02-20
Feature: `lecture-index-azure-search-integration`

## Research Method

- Local artifact review:
  - `docs/SPEC.md`
  - current FastAPI code and tests
- External research:
  - Microsoft official docs (Azure AI Search + Python SDK)
- Note: Gemini CLI was not executable in this shell (`GEMINI_API_KEY` missing), so external research was completed via official documentation directly.

## 1. Product Constraints from SPEC

From `docs/SPEC.md`:
- `lecture_chunks` must be persisted in SQLite and also indexed into Azure AI Search.
- Azure AI Search index name for lecture QA is `lecture_index`.
- Finalize timing rule: indexing is tied to lecture finalize flow.
- Failure behavior: if indexing fails, return with `qa_index_built=false` and allow re-run.
- Retrieval rule target: session-scoped retrieval (`session_id` filtering is mandatory).

## 2. Azure AI Search Findings (Official)

1. Python quickstart demonstrates index lifecycle + uploads + queries.
- `SearchIndexClient.create_or_update_index(...)`
- `SearchClient.upload_documents(...)`
- Search queries with filters and vector/hybrid options
- Source: https://learn.microsoft.com/en-us/azure/search/search-get-started-text

2. Async SDK is available and suitable for FastAPI.
- `azure.search.documents.aio.SearchClient`
- `azure.search.documents.indexes.aio.SearchIndexClient`
- Source:
  - https://learn.microsoft.com/en-us/python/api/azure-search-documents/azure.search.documents.aio.searchclient
  - https://learn.microsoft.com/en-us/python/api/azure-search-documents/azure.search.documents.indexes.aio.searchindexclient

3. Safe document upsert path exists.
- `merge_or_upload_documents(...)` supports idempotent-like upsert behavior without pre-read.
- Source: `SearchClient` API reference above

4. Query interface supports hybrid retrieval and filter controls.
- `search(...)` can accept keyword text + vector queries + filter.
- `vector_filter_mode` allows controlling filter timing around vector search.
- Source: `SearchClient.search(...)` API reference above

5. Vector fields require explicit schema setup.
- `SearchField` supports vector dimensions/profile configuration.
- Embedding dimensionality must match index schema.
- Source: https://learn.microsoft.com/en-us/python/api/azure-search-documents/azure.search.documents.indexes.models.searchfield

6. Index alias APIs exist.
- `SearchIndexClient` includes alias operations (`create_or_update_alias`, etc.) for index-switch patterns.
- Useful for zero/low-downtime schema evolution.
- Source: `SearchIndexClient` API reference above

## 3. Design Implications for This Codebase

1. Keep `lecture_chunks` as canonical source of truth.
- Build search documents from `lecture_chunks` + `lecture_sessions` metadata.

2. Preserve ownership and isolation guarantees.
- Retrieval must always apply `session_id` filter before returning candidates to QA service.

3. Finalize path should be authoritative for index sync.
- Rebuild chunks -> push to Azure index -> update `indexed_to_search` flags -> set `qa_index_built`.

4. Maintain deterministic fallback.
- If Azure Search is disabled or errors, keep BM25 fallback path to avoid feature outage in dev.

5. Use strict config toggle.
- `azure_search_enabled=false` should fully bypass Azure clients.

## 4. Proposed `lecture_index` Field Mapping

- `chunk_id` (key)
- `session_id` (filterable)
- `course_name` (searchable + filterable)
- `date` (filterable)
- `chunk_type` (filterable)
- `start_ms`, `end_ms` (filterable + sortable)
- `speech_text`, `visual_text`, `summary_text` (searchable)
- `keywords` (collection; searchable/filterable as needed)
- `embedding` (vector; optional in phase-1 if embeddings not ready)
- `lang` (filterable)

This aligns with SPEC section 12.1.

## 5. Risks and Mitigations

1. Risk: partial indexing failures create inconsistent state.
- Mitigation: inspect per-document indexing results and update `indexed_to_search` only for successful chunk IDs.

2. Risk: index schema drift from app fields.
- Mitigation: maintain schema builder in one module; add contract tests with expected field list.

3. Risk: production secret handling.
- Mitigation: keep keys in Key Vault and environment injection; never log credentials.

4. Risk: retrieval relevance for Japanese text.
- Mitigation: start with lexical + optional vector hybrid; defer tokenizer improvements to follow-up iteration.

## 6. Open Questions (Need User Approval)

1. Retrieval cutover policy:
- Should `/lecture/qa/ask` default to Azure retrieval immediately when enabled, or run Azure+BM25 dual-read during a burn-in phase?

2. Vector rollout:
- Do we include vector fields and embedding generation in this feature scope, or ship lexical first and add vectors next?

3. Index lifecycle:
- Keep a single durable `lecture_index`, or adopt versioned indexes + alias switching now?
