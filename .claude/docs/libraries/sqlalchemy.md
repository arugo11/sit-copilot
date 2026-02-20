# SQLAlchemy Constraints

Library: SQLAlchemy 2.0+
Version: >=2.0
Async Driver: aiosqlite (dev), asyncpg (prod - PostgreSQL)

## Key Constraints

### Async Operations
- **Must use `await`** for all database operations
- Never mix sync `Session` with `async def` routes
- Use `AsyncSession`, not sync `Session`

### Session Management
```python
# Correct
async with AsyncSessionLocal() as session:
    await session.execute(query)
    await session.commit()

# Incorrect - blocks event loop
with SessionLocal() as session:
    session.execute(query)  # Sync in async context
```

### Connection String Format
```python
# SQLite (development/testing)
"sqlite+aiosqlite:///./app.db"
"sqlite+aiosqlite:///:memory:"  # In-memory for tests

# PostgreSQL (production)
"postgresql+asyncpg://user:pass@localhost/dbname"
```

### Critical Configuration
```python
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # REQUIRED: Prevents lazy loading errors
)
```

### Model Definition (2.0 Style)
```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
```

### Query Patterns
```python
# Select
result = await db.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()

# Insert
db.add(User(name="Alice"))
await db.commit()
await db.refresh(user)  # Get generated fields

# Update
user.name = "Bob"
await db.commit()
```

## Common Pitfalls

1. **Forgetting `await`**: Always await async operations
2. **Lazy loading after commit**: Set `expire_on_commit=False` to avoid
3. **Not closing sessions**: Use context managers or dependency injection
4. **Mixing sync/async**: Use async throughout in FastAPI

## References
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
