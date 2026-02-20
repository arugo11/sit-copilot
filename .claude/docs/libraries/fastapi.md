# FastAPI Constraints

Library: FastAPI
Version: >=0.115

## Key Constraints

### API Path Prefix

All endpoints must use `/api/v4/` prefix:
```python
# app/main.py
app.include_router(settings_router, prefix="/api/v4", tags=["settings"])
```

### Dependency Injection

```python
from fastapi import Depends

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

# Use in routes
@router.get("/settings/me")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ...
```

### Router Structure

```
app/
├── api/
│   └── v4/
│       ├── __init__.py
│       ├── settings.py     # Settings routes
│       └── health.py       # Health check
├── core/
│   ├── config.py           # Settings
│   └── deps.py             # Dependencies (get_db, etc.)
├── db/
│   ├── __init__.py
│   ├── base.py             # Base class
│   └── session.py          # Session factory
├── models/
│   └── user.py             # SQLAlchemy models
├── schemas/
│   └── settings.py         # Pydantic schemas
└── services/
    └── settings_service.py # Business logic
```

### Thin Router Pattern

Routes should be thin - business logic goes in services:
```python
# app/api/v4/settings.py - Thin router
@router.get("/settings/me")
async def get_settings(
    user_id: int = Depends(get_current_user_id),
    service: SettingsService = Depends(),
) -> SettingsResponse:
    return await service.get_user_settings(user_id)

# app/services/settings_service.py - Business logic
class SettingsService:
    async def get_user_settings(self, user_id: int) -> SettingsResponse:
        # Complex logic here
        pass
```

### Error Responses

**Standard format for validation errors (400/422)**
```json
{
  "code": 400,
  "message": "Validation error",
  "detail": {...}
}
```

**HTTPException for simple cases**
```python
from fastapi import HTTPException

if not user:
    raise HTTPException(status_code=404, detail="User not found")
```

**Custom exception for complex cases**
```python
class ApiException(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
```

## Common Pitfalls

1. **Business logic in routes**: Move to services layer
2. **Direct DB access without dependency**: Use `Depends(get_db)`
3. **Missing `async/await`**: FastAPI is async-first
4. **Inconsistent error responses**: Use standard format

## References
- [FastAPI Official Documentation](https://fastapi.tiangolo.com/)
