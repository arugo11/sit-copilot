# Sprint1 Codebase Analysis

## Executive Summary

This is a FastAPI backend project (`sit-copilot`) following a modular layered architecture. The codebase uses modern Python 3.11+ with async/await patterns, Pydantic v2 for validation, and follows TDD principles.

---

## 1. Directory Structure

```
sit-copilot/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI instance & root router
│   ├── api/
│   │   ├── __init__.py
│   │   └── v4/
│   │       ├── __init__.py
│   │       └── health.py       # Health check endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py           # Pydantic Settings configuration
│   └── schemas/
│       ├── __init__.py
│       └── health.py           # Pydantic response models
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   └── api/
│       ├── __init__.py
│       └── test_health.py      # Health endpoint tests
├── pyproject.toml              # Dependencies & tool config
└── uv.lock                     # Locked dependencies
```

---

## 2. Key Modules & Responsibilities

| Module | Responsibility | Key Patterns |
|--------|---------------|--------------|
| `app/main.py` | FastAPI app initialization, router inclusion | Single app instance, versioned routing |
| `app/api/v4/` | HTTP endpoints by feature | `APIRouter` with prefix/tags |
| `app/schemas/` | Pydantic models for request/response | `BaseModel` with type hints |
| `app/core/` | Configuration, shared utilities | `BaseSettings` for env vars |
| `tests/conftest.py` | Shared test fixtures | `AsyncClient` with `ASGITransport` |
| `tests/api/` | Endpoint tests mirroring api structure | AAA pattern, async tests |

---

## 3. Existing Patterns & Conventions

### 3.1 Code Style

- **Type hints**: All functions use `-> ReturnType` annotations
- **Docstrings**: Google-style docstrings on modules and functions
- **Async/await**: All endpoints are async
- **Early returns**: Functions return directly without intermediate variables

### 3.2 API Routing Pattern

```python
# app/api/v4/health.py
router = APIRouter(prefix="/health", tags=["health"])

@router.get("", status_code=status.HTTP_200_OK, response_model=HealthResponse)
async def get_health() -> HealthResponse:
    return HealthResponse(status="healthy")

# app/main.py
app.include_router(health_api.router, prefix="/api/v4")
```

**Convention**: 
- Each feature gets its own router file in `app/api/v4/`
- Routers use descriptive prefix and tags
- Endpoints use explicit status codes and response models
- All routers included in main with `/api/v4` prefix

### 3.3 Configuration Pattern

```python
# app/core/config.py
class Settings(BaseSettings):
    app_name: str = "SIT Copilot"
    version: str = "0.1.0"
    debug: bool = False
    
    model_config = {"env_file": ".env"}

settings = Settings()  # Singleton instance
```

**Convention**:
- Pydantic Settings for type-safe configuration
- Environment variables override defaults
- Singleton `settings` instance imported elsewhere

### 3.4 Schema Pattern

```python
# app/schemas/health.py
class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
```

**Convention**:
- Request/Response models in `app/schemas/`
- Default values for optional fields
- Separate from domain models (future)

---

## 4. Dependencies & Tech Stack

```toml
[project]
name = "sit-copilot"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "fastapi>=0.110",           # Web framework
    "pydantic-settings>=2.13.1", # Configuration
    "uvicorn[standard]>=0.32",   # ASGI server
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "pytest-mock>=3.12",
    "pytest-asyncio>=0.25.1",    # Async test support
    "httpx>=0.26",               # Async HTTP client
    "ruff>=0.8",                 # Linter & formatter
    "mypy>=1.8",                 # Type checker
]
```

### Tool Configuration

| Tool | Config Key | Settings |
|------|-----------|----------|
| pytest | `asyncio_mode` | `"auto"` (required for FastAPI) |
| ruff | `select` | `["E", "W", "F", "I", "B", "UP", "ASYNC"]` |
| mypy | `strict` | `true` (strict type checking) |

---

## 5. Test Structure & Patterns

### 5.1 Fixture Pattern

```python
# tests/conftest.py
@pytest.fixture
async def async_client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
```

**Pattern**: ASGITransport for direct FastAPI testing (no HTTP server needed)

### 5.2 AAA Test Pattern

```python
@pytest.mark.asyncio
async def test_health_endpoint_returns_200(async_client: AsyncClient) -> None:
    # Arrange
    endpoint = "/api/v4/health"
    
    # Act
    response = await async_client.get(endpoint)
    
    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

**Naming convention**: `test_{target}_{condition}_{expected_result}`

### 5.3 Test Organization

- Tests mirror API structure: `tests/api/test_health.py` tests `app/api/v4/health.py`
- Each endpoint has multiple tests for:
  - Status code verification
  - Response structure validation
  - Content type verification
  - Edge cases (as needed)

---

## 6. Recommendations for SQLite Persistence & Settings API

### 6.1 Recommended Directory Structure

```
app/
├── models/                    # NEW: Database models
│   ├── __init__.py
│   └── setting.py             # Setting ORM model
├── db/                        # NEW: Database layer
│   ├── __init__.py
│   ├── database.py            # SQLite connection management
│   └── repositories/          # Repository pattern
│       ├── __init__.py
│       └── setting_repo.py    # Settings CRUD operations
├── services/                  # NEW: Business logic
│   ├── __init__.py
│   └── setting_service.py     # Settings service layer
├── api/v4/
│   └── settings.py            # NEW: Settings endpoints
└── schemas/
    └── setting.py             # NEW: Settings request/response models
```

### 6.2 Database Configuration Extension

**File**: `app/core/config.py`

```python
class Settings(BaseSettings):
    # ... existing fields ...
    
    # Database settings
    database_url: str = "sqlite+aiosqlite:///./sit-copilot.db"
    echo_sql: bool = False
```

### 6.3 Settings API Test Structure

**File**: `tests/api/test_settings.py`

```python
@pytest.mark.asyncio
async def test_get_settings_returns_200(async_client: AsyncClient) -> None:
    # Arrange
    # Act
    response = await async_client.get("/api/v4/settings")
    # Assert
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_create_setting_returns_201(async_client: AsyncClient) -> None:
    # Arrange
    payload = {"key": "theme", "value": "dark"}
    # Act
    response = await async_client.post("/api/v4/settings", json=payload)
    # Assert
    assert response.status_code == 201

@pytest.mark.asyncio
async def test_update_setting_returns_200(async_client: AsyncClient) -> None:
    # Similar pattern for PUT/PATCH

@pytest.mark.asyncio
async def test_delete_setting_returns_204(async_client: AsyncClient) -> None:
    # Similar pattern for DELETE
```

### 6.4 Recommended Dependencies

```toml
dependencies = [
    # ... existing ...
    "aiosqlite>=0.20",         # Async SQLite support
    "sqlalchemy[asyncio]>=2.0", # ORM with async support
]
```

### 6.5 Key Conventions to Follow

1. **Async everywhere**: All DB operations must be async
2. **Type hints**: All functions must have return types
3. **AAA tests**: All tests follow Arrange-Act-Assert
4. **Response models**: All endpoints define explicit response_model
5. **Status codes**: Use explicit HTTP status codes
6. **Error handling**: Use FastAPI exception handlers
7. **Coverage**: Target 80%+ with pytest-cov

---

## 7. Key Files Reference

| File | Purpose |
|------|---------|
| `app/main.py` | Add new router includes here |
| `app/core/config.py` | Add DB configuration here |
| `tests/conftest.py` | Add DB fixture for test isolation |
| `pyproject.toml` | Add new dependencies here |
