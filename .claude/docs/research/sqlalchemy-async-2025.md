# SQLAlchemy Async Research 2025

## Date: 2026-02-21

## Purpose
Validation of design decisions for Sprint1 settings-api-and-db project.

---

## 1. SQLite JSON Column with SQLAlchemy

### Finding: MutableDict is Still Valid BUT Has Known Issues

**Status**: `MutableDict` is **NOT deprecated** in 2025, but has important caveats.

### Critical Issues Discovered

#### Issue 1: Mutation Tracking Breaks with Inheritance (August 2025)
From GitHub discussion [fastapi/sqlmodel#1558](https://github.com/fastapi/sqlmodel/discussions/1558):

When using SQLModel with inheritance, `MutableDict` tracking **does NOT work reliably**:
- Objects added and committed don't appear in `session.dirty` when JSON is mutated
- Changes are silently lost on commit

**Workaround**: Still use `flag_modified()` manually

#### Issue 2: Direct Mutations Don't Trigger Dirty Checking
From [CSDN article](https://blog.csdn.net/nqs__/article/details/136352875) (April 2025):

```python
# WRONG - Changes not saved
user.settings['theme'] = 'dark'
await session.commit()  # Changes lost!

# CORRECT - Always use flag_modified
user.settings['theme'] = 'dark'
from sqlalchemy.orm.attributes import flag_modified
flag_modified(user, 'settings')
await session.commit()  # Saved correctly
```

### Recommended Approach for Sprint1

**Option A: JSON + MutableDict (with flag_modified)**
```python
from sqlalchemy import Column, Integer, String, JSON
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm.attributes import flag_modified

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    settings = Column(MutableDict.as_mutable(JSON), default=lambda: {})

# Service layer must always call flag_modified
def update_setting(user: User, key: str, value: Any):
    user.settings[key] = value
    flag_modified(user, 'settings')
```

**Pros**: Automatic dict-to-string conversion
**Cons**: Must remember `flag_modified()` on every mutation

**Option B: Custom TypeDecorator (Simpler, More Explicit)**
```python
from sqlalchemy import TypeDecorator, TEXT
import json

class JSONType(TypeDecorator):
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return value

class User(Base):
    __tablename__ = "users"
    settings = Column(JSONType, default=lambda: {})

# Always use flag_modified for mutations
user.settings = {'theme': 'dark'}  # Full replacement
# OR
user.settings['theme'] = 'dark'
flag_modified(user, 'settings')
```

**Pros**: Simpler, no dependency on MutableDict extension
**Cons**: Manual JSON serialization/deserialization

### Recommendation for Sprint1

**Use Option A (JSON + MutableDict)** but with these rules:

1. **Always use `flag_modified()`** after mutating the JSON field
2. **Never use mutable default arguments** - use `default=lambda: {}`
3. **Write a helper in service layer** to avoid forgetting flag_modified

```python
# app/services/settings_service.py
from sqlalchemy.orm.attributes import flag_modified

class SettingsService:
    async def update_setting(self, user: User, key: str, value: Any) -> User:
        if not user.settings:
            user.settings = {}
        user.settings[key] = value
        flag_modified(user, 'settings')
        return user
```

### Sources
- [SQLModel Mutation Tracking Issue](https://github.com/fastapi/sqlmodel/discussions/1558) - August 2025
- [JSON Field Save Issue & Solution](https://blog.csdn.net/nqs__/article/details/136352875) - April 2025

---

## 2. aiosqlite Version

### Latest Stable Version

**aiosqlite 0.21.0** - Released February 3, 2025

From [PyPI](https://pypi.org/project/aiosqlite/):
- Compatible with Python 3.8+
- MIT licensed
- Active maintenance (latest release Feb 2025)
- No breaking changes reported in recent versions

### Installation

```bash
uv add aiosqlite>=0.21.0
```

### Key Points
- Stable, mature library
- Single shared thread per connection (non-blocking design)
- Replicates standard sqlite3 module with async versions
- Context manager support for automatic cleanup

### Breaking Changes
**None reported** for version 0.21.0. The library maintains backward compatibility.

---

## 3. Session Management Pattern Validation

### Proposed Pattern (from Codex)

```python
async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

### Assessment: PARTIALLY CORRECT, Has Issues

**Problem**: No explicit `await session.commit()` on success path.

**Issue**: The pattern relies on implicit behavior or manual commits in routes. This can lead to:
1. Uncommitted transactions if routes forget to commit
2. Inconsistent behavior across endpoints

### Corrected 2025 Best Practice Pattern

**Option A: Auto-commit on success (RECOMMENDED)**
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # Commit on success
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

This ensures:
- Transactions commit automatically if no exception
- Rollback on any exception
- Session always closes

**Option B: Manual commit in routes (also valid)**
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Route must explicitly commit
@router.post("/settings")
async def update_settings(
    data: SettingsUpdate,
    db: AsyncSession = Depends(get_db)
):
    # ... update logic ...
    await db.commit()  # Explicit commit
    return result
```

### Recommendation for Sprint1

**Use Option A (Auto-commit on success)** for simplicity and consistency:

```python
# app/core/deps.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Rationale**:
- Simpler route handlers (no explicit commit needed)
- Consistent transaction handling
- Matches most FastAPI + SQLAlchemy examples in 2025

**Note**: For routes that need more control (multi-step transactions), you can create a separate dependency without auto-commit.

---

## Summary of Recommendations

| Decision | Recommendation | Rationale |
|----------|----------------|-----------|
| JSON column | `JSON` + `MutableDict` | Standard SQLAlchemy approach |
| Mutation tracking | Always use `flag_modified()` | Reliable mutation detection |
| Default value | `default=lambda: {}` | Avoid shared mutable default |
| aiosqlite version | `>=0.21.0` | Latest stable (Feb 2025) |
| Session pattern | Auto-commit on success | Simpler, consistent behavior |

---

## Sources Consulted

1. [SQLModel Mutation Tracking Issue #1558](https://github.com/fastapi/sqlmodel/discussions/1558) - August 2025
2. [JSON Field Save Issue & Solution](https://blog.csdn.net/nqs__/article/details/136352875) - April 2025
3. [PyPI: aiosqlite 0.21.0](https://pypi.org/project/aiosqlite/) - February 2025
4. [FastAPI + SQLAlchemy Async Best Practices](https://www.juejin.cn/post/7570903763722289162) - Previous research
