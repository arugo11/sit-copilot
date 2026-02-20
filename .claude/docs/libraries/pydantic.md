# Pydantic Constraints

Library: Pydantic
Version: >=2.0

## Key Constraints

### v2 Configuration Changes

**v1 vs v2**
```python
# v1 (deprecated)
class UserSchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

# v2 (current)
class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
```

### SQLAlchemy Integration

```python
from pydantic import BaseModel, ConfigDict

# Reading from ORM objects
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str

# Usage
user_orm = await db.get(User, 1)
user_response = UserResponse.model_validate(user_orm)
```

### Validation Error Responses

FastAPI automatically returns 422 for validation errors:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "email"],
      "msg": "Field required",
      "input": {"name": "Alice"}
    }
  ]
}
```

### Email Validation

```python
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr  # Requires: `uv add pydantic[email]`
```

### Common Patterns

```python
# Request body (no ORM)
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr

# Response (from ORM)
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str

# Update (partial)
class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
```

### Methods

| Method | Purpose |
|--------|---------|
| `model_validate(obj)` | Convert from ORM/dict to Pydantic |
| `model_dump()` | Convert to dict |
| `model_dump_json()` | Convert to JSON string |
| `model_validate_json()` | Parse JSON string |

## Common Pitfalls

1. **Using v1 `orm_mode`**: Use `from_attributes=True` in v2
2. **Using `parse_obj()`**: Use `model_validate()` in v2
3. **Forgetting `from_attributes`**: Required for ORM integration
4. **Missing `pydantic[email]`**: Required for `EmailStr` type

## References
- [Pydantic v2 Migration Guide](https://docs.pydantic.dev/latest/migration/)
