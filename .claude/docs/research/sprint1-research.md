# Sprint1 Settings API & DB Research

## Date: 2026-02-21

## Topics Researched

1. SQLAlchemy 2.0 async patterns with aiosqlite
2. FastAPI dependency injection for DB sessions
3. Test database setup best practices (rollback per test)
4. Pydantic v2 + SQLAlchemy integration
5. FastAPI error handling patterns

---

## 1. SQLAlchemy 2.0 Async Patterns with aiosqlite

### Key Findings

**Native Async Support (SQLAlchemy 2.0+)**
- SQLAlchemy 2.0 provides native asyncio support - no third-party wrappers needed
- Use `aiosqlite` for SQLite async operations in development/testing

**Essential Dependencies**
```bash
uv add "sqlalchemy[asyncio]>=2.0" aiosqlite
```

**Core Setup Pattern**
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Base class for models
class Base(DeclarativeBase):
    pass

# Create async engine
engine = create_async_engine(
    "sqlite+aiosqlite:///./app.db",
    echo=False,  # Set True for SQL logging in dev
    pool_pre_ping=True,  # Enable heartbeat connection checks
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent lazy loading errors
)
```

**Modern Model Definitions with Type Hints**
```python
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
```

**Critical Best Practices**
- Always use `await` for database operations: `await db.execute()`, `await db.commit()`
- Never use synchronous operations in `async def` - blocks event loop
- Use `async with` context managers for session lifecycle
- Set `expire_on_commit=False` to prevent lazy loading errors

### Sources
- [CSDN: FastAPI + SQLAlchemy 2.0 Async Complete Engineering Practice](https://www.juejin.cn/post/7570903763722289162)
- [CSDN: How to Integrate SQLAlchemy 2.0 in FastAPI](https://m.blog.csdn.net/varchat/article/details/157245139)

---

## 2. FastAPI Dependency Injection for DB Sessions

### Key Findings

**Dependency Injection Pattern**
```python
from fastapi import Depends
from typing import AsyncGenerator

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency with automatic cleanup"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Use in Routes**
```python
from sqlalchemy import select

@app.get("/users")
async def get_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return users

@app.post("/users")
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = User(**user.model_dump())
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user
```

**Key Benefits**
- Request-level sessions: Each request gets independent session
- Automatic cleanup with context manager
- Transaction safety: Auto rollback on exceptions
- Thread safety: FastAPI executes dependencies independently per request

### Sources
- [CSDN: FastAPI Database实战](https://www.cnblogs.com/ymtianyu/p/19480142)
- [Juejin: FastAPI x SQLAlchemy 2.0 Async](https://www.juejin.cn/post/7570903763722289162)

---

## 3. Test Database Setup Best Practices

### Key Findings

**In-Memory SQLite for Testing**
```python
# conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(test_engine):
    """Create isolated session with rollback per test"""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        # Create tables
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Use nested transaction for rollback
        async with session.begin_nested():
            yield session

        # Rollback happens automatically on exit
```

**Alternative: Session-scoped Rollback Pattern**
```python
@pytest.fixture(scope="function")
async def db_session():
    async with AsyncTestingSessionLocal() as session:
        async with session.begin_nested():  # CREATE SAVEPOINT
            yield session
        # Auto rollback on exit
```

**Key Best Practices**
- Use in-memory SQLite for test speed
- Function-scoped fixtures for test isolation
- Use `begin_nested()` to create SAVEPOINTs
- Automatic rollback prevents test pollution
- Configure `asyncio_mode = "auto"` in pyproject.toml

### Sources
- [CSDN: FastAPI + SQLAlchemy Async Testing](https://m.blog.csdn.net/qq_37703224/article/details/154663985)

---

## 4. Pydantic v2 + SQLAlchemy Integration

### Key Findings

**Configuration Change: `from_attributes=True`**

In Pydantic v2, the configuration has changed from v1:
- **Pydantic v1**: Used `orm_mode = True`
- **Pydantic v2**: Uses `from_attributes = True` (via `ConfigDict`)

**Basic Setup**
```python
from pydantic import BaseModel, ConfigDict

# SQLAlchemy Model
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)

# Pydantic v2 Schema
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
```

**Alternative Configuration Style**
```python
class UserResponse(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True
```

**Usage**
```python
# Convert SQLAlchemy to Pydantic
user_db = await db.get(User, 1)
user_response = UserResponse.model_validate(user_db)

# Convert to JSON
json_data = user_response.model_dump_json()
```

**Key Points**
- `from_attributes=True` allows reading from ORM object attributes
- Field names must match between SQLAlchemy and Pydantic models
- Provides type-safe model conversion between layers
- Use `model_validate()` instead of `parse_obj()` (v1)

### Sources
- [PHP.cn: SQLAlchemy 2.0 and Pydantic Type-Safe Model Conversion](https://m.php.cn/faq/1773349.html)

---

## 5. FastAPI Error Handling Patterns

### Key Findings

**Standard Error Response Model**
```python
from pydantic import BaseModel
from typing import Optional

class ErrorResponse(BaseModel):
    code: int
    message: str
    detail: Optional[str] = None
    request_id: Optional[str] = None
```

**Custom Exception Handler**
```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail
        }
    )

# Global exception handler
@app.exception_handler(Exception)
async def universal_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "Internal Server Error",
            "detail": str(exc) if app.debug else None
        }
    )
```

**Custom Business Exception**
```python
class BusinessException(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    return JSONResponse(
        status_code=400,
        content={
            "code": exc.code,
            "message": exc.message
        }
    )
```

**4 Methods for Exception Handling**
1. `raise HTTPException` - Simple, built-in
2. Custom exception inheriting from `HTTPException`
3. Global exception handlers with `@app.exception_handler()`
4. Custom business exception classes

### Sources
- [FastAPI Official: Handling Errors](https://fastapi.org.cn/tutorial/handling-errors/)
- [CNBlogs: FastAPI Exception Handling Complete Guide](https://www.cnblogs.com/ymtianyu/articles/19536459.html)
- [Tencent Cloud: HTTP Status Codes and Exception Handling](https://cloud.tencent.com.cn/developer/article/2617631)

---

## Summary of Recommendations

### For Sprint1 Implementation:

1. **Database Layer**
   - Use SQLAlchemy 2.0 with `aiosqlite` for async operations
   - Use `async_sessionmaker` with `expire_on_commit=False`
   - Modern models with `Mapped[]` type hints

2. **Dependency Injection**
   - Create `get_db()` dependency with automatic cleanup
   - Use `Depends(get_db)` in all routes

3. **Testing**
   - In-memory SQLite: `sqlite+aiosqlite:///:memory:`
   - Function-scoped fixtures with `begin_nested()` rollback
   - `asyncio_mode = "auto"` in pyproject.toml

4. **Schemas**
   - Use `from_attributes=True` in Pydantic v2
   - Use `model_validate()` for ORM to Pydantic conversion

5. **Error Handling**
   - Create `ErrorResponse` schema for consistent format
   - Global exception handler for unhandled exceptions
   - Custom `BusinessException` for business logic errors
