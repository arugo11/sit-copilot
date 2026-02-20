# pytest-asyncio Constraints

Library: pytest-asyncio
Version: >=0.23

## Key Constraints

### Required Configuration

**pyproject.toml**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

This is **required** for FastAPI async testing. Without it, you must mark every test with `@pytest.mark.asyncio`.

### Async Fixtures

```python
import pytest

# Correct: async fixture
@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session

# Also correct: explicit decorator
@pytest.mark.asyncio
async def test_user_creation(db_session):
    # ...
```

### Test Pattern with ASGITransport

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.fixture
async def client():
    """AsyncClient with ASGITransport (2025 best practice)"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/v4/health")
    assert response.status_code == 200
```

### Test Database Rollback Pattern

```python
@pytest.fixture(scope="function")
async def db_session(test_engine):
    """Isolated session with automatic rollback"""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        # Create tables
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Nested transaction for rollback
        async with session.begin_nested():
            yield session

        # Auto rollback on exit
```

## Common Pitfalls

1. **Missing `asyncio_mode = "auto"`**: Must be in pyproject.toml
2. **Using sync `pytest.fixture` with async**: Use `@pytest.fixture` (auto-detects)
3. **Not awaiting operations**: All DB operations must be awaited
4. **Test pollution**: Use `begin_nested()` for rollback isolation

## References
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
