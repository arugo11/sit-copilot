# azure-search-documents Notes for SIT Copilot

Date: 2026-02-20
Package: `azure-search-documents` (Python SDK)
Use Case: Lecture index ingestion/retrieval for Azure AI Search

## Recommended Usage

- Client split:
  - `SearchIndexClient`: create/update index (schema lifecycle)
  - `SearchClient`: document upload/merge/search
- Prefer async clients (`azure.search.documents.aio`) in FastAPI services.

## Key APIs

- Index operations:
  - `create_or_update_index(...)`
  - alias operations are available (`create_or_update_alias`, `delete_alias`, `get_alias`)
- Document operations:
  - `upload_documents(...)`
  - `merge_or_upload_documents(...)`
  - `delete_documents(...)`
- Query operations:
  - `search(...)` supports `filter`, semantic parameters, vector queries, and `vector_filter_mode`

## Practical Constraints

- Document keys must be stable and unique (`chunk_id` fits this role).
- For partial updates, `merge_or_upload_documents` is safer than manual existence checks.
- Batch indexing can partially fail; inspect per-document indexing results.
- Filter by `session_id` at query time to enforce lecture session isolation.

## Index Schema Mapping Guidance

- Use filterable fields for session/course/date/lang boundaries.
- Keep searchable text in speech/visual/summary fields.
- Add vector field with fixed dimensions matching the embedding model.
- For hybrid retrieval, send both keyword query and vector query in one request.

## Security / Auth

- Dev/MVP: API key via `AzureKeyCredential` is simplest.
- Production: prefer Entra ID / managed identity where feasible.

## Official References

- Python quickstart (index + upload + query examples):
  - https://learn.microsoft.com/en-us/azure/search/search-get-started-text
- Python SDK reference (`aio` clients):
  - https://learn.microsoft.com/en-us/python/api/azure-search-documents/azure.search.documents.aio.searchclient
  - https://learn.microsoft.com/en-us/python/api/azure-search-documents/azure.search.documents.indexes.aio.searchindexclient
  - https://learn.microsoft.com/en-us/python/api/azure-search-documents/azure.search.documents.indexes.models.searchfield
