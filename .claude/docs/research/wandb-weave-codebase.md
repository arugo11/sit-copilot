# WandB Weave Integration - Codebase Analysis

## Overview
SIT Copilot is a FastAPI-based lecture assistant application with SQLite persistence, Azure OpenAI integration, and comprehensive QA/transcript features.

## Directory Structure

```
app/
├── api/v4/          # API route handlers
├── core/            # Configuration, auth, errors
├── db/              # Database session management
├── models/          # SQLAlchemy ORM models
├── schemas/         # Pydantic request/response schemas
└── services/        # Business logic layer
tests/
├── api/v4/          # API endpoint tests
└── unit/            # Unit tests for services/schemas
```

## Architecture Patterns

### Layered Architecture
```
API Layer (routes) → Service Layer (business logic) → Model Layer (database) → DB Layer (session)
```

### Service Pattern
All services follow a Protocol-based interface pattern:

```python
class FeatureService(Protocol):
    async def operation(self, ...) -> Response:
        ...

class SqlAlchemyFeatureService:
    def __init__(self, db: AsyncSession, dependencies...):
        ...

    async def operation(self, ...):
        # Implementation
```

### Dependency Injection
- FastAPI `Depends()` for service resolution
- Provider functions in route modules: `get_*_service()`
- Configuration-based conditional service selection (Azure vs Noop)

## Configuration Management

### Settings Pattern (app/core/config.py)
- Pydantic Settings `BaseSettings`
- Environment variable loading from `.env`, `.env.azure.generated`
- Feature flags: `azure_openai_enabled`, `azure_vision_enabled`, `azure_search_enabled`
- Azure-specific settings with validation

### Existing Azure Integrations
| Service | Config Pattern | Fallback |
|---------|---------------|----------|
| OpenAI | `azure_openai_*` settings | UnavailableLectureSummaryGeneratorService |
| Vision | `azure_vision_*` settings | NoopVisionOCRService |
| Search | `azure_search_*` settings | BM25LectureIndexService |

## Service Integration Points

### Key Services for Weave Observation
1. **LectureQAService** (`app/services/lecture_qa_service.py`)
   - Main QA orchestration with timing metrics (`perf_counter()`)
   - Already tracks `latency_ms` in QATurn persistence
   - Retrieval → Answer → Verify → Persist pipeline

2. **AzureOpenAILectureAnswererService** (`app/services/lecture_answerer_service.py`)
   - Direct Azure OpenAI API calls
   - Prompt building and response parsing
   - Error handling with fallback

3. **LectureRetrievalService** (`app/services/lecture_retrieval_service.py`)
   - BM25 and Azure Search implementations
   - Source scoring and ranking

### Latency Tracking Pattern
```python
from time import perf_counter

started_at = perf_counter()
# ... operation ...
latency_ms = max(0, int((perf_counter() - started_at) * 1000))
```

## Database Models

### QATurn Model (app/models/qa_turn.py)
- Already captures: `question`, `answer`, `confidence`, `latency_ms`
- JSON fields: `citations_json`, `retrieved_chunk_ids_json`
- Feature flag: `verifier_supported`

### Key Models for Observation
| Model | Relevant Fields |
|-------|----------------|
| QATurn | latency_ms, confidence, citations_json |
| SpeechEvent | confidence, start_ms, end_ms |
| SummaryWindow | summary_text, key_terms_json |

## Test Structure

### Fixtures (tests/conftest.py)
- `test_engine`: In-memory SQLite
- `db_session`: Async session with rollback
- `async_client`: ASGITransport for API testing
- `mock_summary_generator`: Deterministic mock for testing

### Test Patterns
```python
async def test_feature_with_condition():
    # Arrange
    setup_data = {...}
    
    # Act
    result = await service.operation(setup_data)
    
    # Assert
    assert result.field == expected
```

## Dependencies (pyproject.toml)

### Core Stack
- FastAPI 0.110+
- SQLAlchemy 2.0 (async)
- aiosqlite 0.21+
- Pydantic Settings 2.13+

### External Services
- azure-ai-vision-imageanalysis
- azure-search-documents
- rank-bm25 (local retrieval)

### Dev Tools
- pytest 8.0+, pytest-asyncio, pytest-mock
- ruff (lint/format)
- mypy (type check)

## Integration Strategy for WandB Weave

### Recommended Approach

1. **New Service Module**: `app/services/weave_observer_service.py`
   - Protocol: `WeaveObserverService`
   - Implementation: `WandBWeaveObserverService`
   - Noop fallback: `NoopWeaveObserverService`

2. **Configuration** (`app/core/config.py`)
   ```python
   weave_enabled: bool = False
   weave_project: str = ""
   weave_entity: str = ""
   ```

3. **Dependency Injection Pattern**
   - Add `get_weave_observer_service()` in relevant route modules
   - Inject into services that need observation
   - Graceful fallback when disabled

4. **Observation Points**
   - QA turn completion (question, sources, answer, latency)
   - Retrieval metrics (sources, scores)
   - LLM calls (prompt, response, latency)

5. **Initialization** (app/main.py)
   ```python
   @asynccontextmanager
   async def lifespan(_: FastAPI):
       if settings.weave_enabled:
           initialize_weave(settings.weave_project, settings.weave_entity)
       # ... existing DB setup
   ```

## Key Considerations

1. **Async/Await**: All services are async; Weave integration should be non-blocking
2. **Error Isolation**: Observer failures should not break main functionality
3. **Feature Flag Pattern**: Follow existing Azure-enabled pattern
4. **Type Safety**: Use Protocol for interface, mypy-compatible
5. **Testing**: Mock WeaveObserverService in tests, use Noop variant by default
