# Sprint0 Research: FastAPI Backend Setup Best Practices (2025)

**Research Date**: 2025-02-21
**Researcher**: Researcher Agent
**Target**: FastAPI backend foundation with green pytest and /health endpoint

---

## 1. Project Structure Best Practices

### Recommended Modular Layout (2025 Standard)

```
fastapi-project/
├── app/
│   ├── main.py                 # FastAPI instance initialization
│   ├── api/                    # Route handlers organized by feature
│   │   ├── v1/                 # API versioning
│   │   │   ├── __init__.py
│   │   │   ├── health.py       # Health check endpoint
│   │   │   └── routes.py       # Other endpoints
│   │   └── __init__.py
│   ├── core/                   # Core configurations
│   │   ├── config.py           # Settings, env vars
│   │   └── logging_config.py   # Unified logging
│   ├── schemas/                # Pydantic models (request/response)
│   ├── services/               # Business logic layer
│   └── deps/                   # Dependencies
├── tests/                      # Test files
│   ├── api/
│   ├── conftest.py             # Shared fixtures
│   └── __init__.py
├── pyproject.toml              # Unified dependency management
└── .env.example
```

### Layer Separation Principles

| Layer | Purpose | Rules |
|-------|---------|-------|
| **api/** | Route handlers | Only `@router` decorators, delegate logic to services |
| **schemas/** | Pydantic models | Request/response validation |
| **services/** | Business logic | Pure Python, no FastAPI dependencies |
| **core/** | System-level | Config, DB connections, security |

### Key Trends for 2025

1. **Service Layer Pattern**: Strong separation of business logic from routes
2. **API Versioning**: Using `/api/v1/`, `/api/v2/` structure
3. **Configuration Management**: Centralized `core/config.py` with Pydantic Settings
4. **Unified pyproject.toml**: Single file for dependencies and tool config

---

## 2. Pytest Configuration for FastAPI

### Async Test Fixtures Pattern

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def async_client():
    """Async client for testing FastAPI endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
```

### Test Structure (AAA Pattern)

```python
# tests/api/test_health.py
import pytest

@pytest.mark.asyncio
async def test_health_endpoint_returns_200(async_client):
    # Arrange
    endpoint = "/api/v1/health"

    # Act
    response = await async_client.get(endpoint)

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

### Pytest Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
addopts = [
    "-v",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html",
]
```

### Required Dependencies

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "pytest-mock>=3.12",
    "pytest-asyncio>=0.23",  # Critical for FastAPI async tests
    "httpx>=0.26",           # For AsyncClient
]
```

---

## 3. Ruff and Mypy Configuration

### Ruff Configuration (pyproject.toml)

```toml
[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "UP",     # pyupgrade
    "ASYNC",  # flake8-async (important for FastAPI)
]
ignore = ["E501"]  # formatter handles

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports
```

### Mypy Configuration (pyproject.toml)

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

**Note**: The project spec specifies `ty` (Astral's fast type checker) instead of `mypy`. `ty` is mypy-compatible.

---

## 4. Common Pitfalls: FastAPI + Pytest + Async

### Pitfall 1: Missing pytest-asyncio Configuration

**Problem**: Tests hang or fail with "coroutine was never awaited"

**Solution**: Always set `asyncio_mode = "auto"` in pytest config

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### Pitfall 2: Using TestClient Instead of AsyncClient

**Problem**: Tests fail with "RuntimeError: There is no current event loop"

**Solution**: Use `httpx.AsyncClient` with `ASGITransport`

```python
# Wrong
from fastapi.testclient import TestClient
client = TestClient(app)

# Correct
from httpx import AsyncClient, ASGITransport
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    ...
```

### Pitfall 3: Not Using ASGITransport

**Problem**: Deprecation warnings with httpx 0.26+

**Solution**: Always use `ASGITransport` for FastAPI testing

```python
from httpx import AsyncClient, ASGITransport

transport = ASGITransport(app=app)
```

### Pitfall 4: Forgetting @pytest.mark.asyncio

**Problem**: Tests are collected but not executed

**Solution**: Use `asyncio_mode = "auto"` OR mark each test

```python
@pytest.mark.asyncio
async def test_endpoint():
    ...
```

### Pitfall 5: Database Tests Not Isolated

**Problem**: Tests affect each other's state

**Solution**: Use fixtures with proper teardown

```python
@pytest.fixture
async def db_session():
    async with async_session_maker() as session:
        yield session
        await session.rollback()
```

---

## 5. Health Endpoint Patterns

### Basic Health Check (Minimum Viable)

```python
# app/api/v1/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}
```

### Production-Grade Health Check

```python
# app/api/v1/health.py
from fastapi import APIRouter, HTTPException
from datetime import datetime

router = APIRouter()

@router.get("/health", include_in_schema=False)
async def health_check():
    """
    Health check endpoint for monitoring.
    Returns 200 if service is healthy.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@router.get("/ready")
async def readiness_check():
    """
    Readiness check - validates service can handle traffic.
    Returns 503 if dependencies are not ready.
    """
    # Add dependency checks here (DB, Redis, etc.)
    # For Sprint0, just return OK
    return {"status": "ready"}
```

### Best Practices for Health Endpoints

1. **Exclude from public schema** when sensitive: `include_in_schema=False`
2. **Add middleware exceptions** to bypass auth/CORS
3. **Include timestamps** for monitoring
4. **Keep it fast** - avoid slow DB queries in health checks
5. **Use separate endpoints**: `/health` (liveness) vs `/ready` (readiness)

---

## 6. Tool Commands Summary

```bash
# Install dependencies
uv sync --all-extras

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run ty check app/

# Run tests
uv run pytest -v

# Run tests with coverage
uv run pytest --cov=app --cov-report=term-missing

# Quick test (quiet mode)
uv run pytest -q
```

---

## 7. Version Constraints & Compatibility

| Tool | Recommended Version | Notes |
|------|---------------------|-------|
| Python | 3.11+ | Project requirement (25% faster than 3.10) |
| FastAPI | 0.115.0+ | Full Pydantic v2 support, 30% faster validation |
| pytest | 8.0+ | Latest stable |
| pytest-asyncio | 0.25.1+ (or 1.2.0+) | Latest stable, better event loop for Python 3.11+ |
| httpx | 0.26+ | Required for ASGITransport |
| pytest-cov | 4.1+ | Recommended over coverage.py for FastAPI async |
| ruff | 0.8+ | Full Python 3.11 support |
| ty | Latest | Astral's mypy-compatible checker |

### Compatibility Validation (2025)

**1. FastAPI 0.115+ + pytest-asyncio + Python 3.11**: ✅ Fully Compatible
- pytest-asyncio 0.25.1+ and 1.2.0+ fully support Python 3.11
- FastAPI 0.115.0+ with Pydantic v2 provides optimal performance
- Use `asyncio_mode = "auto"` for best results

**2. Test Client Best Practice**: ✅ httpx.AsyncClient + ASGITransport
- **Recommended**: `httpx.AsyncClient` with `ASGITransport(app=app)`
- **Legacy**: `fastapi.testclient.TestClient` (synchronous, not recommended for new projects)
- ASGITransport eliminates deprecation warnings with httpx 0.26+

**3. ruff + ty Compatibility**: ✅ Excellent
- Both fully support Python 3.11
- ruff has native PEP 695 support (Python 3.11+ generics)
- ty is mypy-compatible and works alongside ruff
- Recommended stack: `uv + ruff + ty` (all Astral tools)

**4. Coverage Tool**: ✅ pytest-cov (Recommended)
- **pytest-cov**: Better for FastAPI async contexts
- **coverage.py**: Can incorrectly mark async code as "missing"
- pytest-cov integrates seamlessly with pytest and pytest-xdist

### 2025 Toolchain Recommendation

```bash
# Modern Python toolchain for FastAPI
uv add fastapi>=0.115.0 httpx>=0.26
uv add --dev pytest>=8.0 pytest-asyncio>=0.25.1 pytest-cov>=4.1 pytest-mock ruff ty
```

---

## 8. Architect Recommendations

### For Architect Teammate

1. **Project Structure**: Use modular layout with `app/api/v1/` for versioning
2. **Configuration**: Centralize in `core/config.py` using Pydantic Settings
3. **Service Layer**: Separate business logic from routes from day one
4. **Testing**: Mirror `app/` structure in `tests/` directory
5. **Dependencies**: Use `uv` exclusively, manage via `pyproject.toml`

### Tool Configuration Requirements

- **pytest**: Must have `asyncio_mode = "auto"` for FastAPI async tests
- **ruff**: Enable `ASYNC` lint rules for FastAPI
- **ty**: Configure `strict = true`, but allow untyped in tests
- **httpx**: Must be 0.26+ for ASGITransport support

---

## Sources

### Project Structure & Best Practices
- [Auth0 FastAPI Best Practices](https://auth0.com/blog/fastapi-best-practices/)
- [FastAPI Health Endpoint Patterns](https://blog.csdn.net/weixin_44262492/article/details/155857595)
- [FastAPI Project Structure 2025](https://www.cnblogs.com/ymtianyu/p/19385007)

### Tool Configuration
- [Mypy Configuration Guide 2025](https://blog.csdn.net/gitblog_01121/article/details/151235373)
- [UV Python Toolchain Guide](https://blog.51cto.com/u_15912723/14458536)
- [Ruff Async Linting Guide](https://m.blog.csdn.net/gitblog_00773/article/details/151450826)

### Testing & Coverage
- [Python Testing Framework 2025](https://m.blog.csdn.net/LogicGlow/article/details/152513277)
- [FastAPI Test Coverage Best Practices](https://juejin.cn/post/7544920804624777270)
- [pytest-cov Usage Guide](https://m.blog.csdn.net/kk_lzvvkpj/article/details/147450593)
- [Async Coverage Testing](https://cloud.tencent.com/developer/article/2530591)

### Compatibility
- [Python 3.11 Performance Analysis](https://blog.csdn.net/2201_76028616/article/details/157835025)
- [FastAPI 0.115 Release Notes](https://github.com/fastapi/fastapi/releases)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
