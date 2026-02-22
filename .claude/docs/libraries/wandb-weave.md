# WandB Weave Library Documentation

> Library: wandb/weave  
> Version: Latest (as of 2025-01)  
> Python: 3.8+  
> License: Apache-2.0

---

## Quick Reference

### Installation

```bash
# Using uv (recommended for SIT Copilot)
uv add weave

# Or pip
pip install weave
```

### Basic Usage

```python
import weave

# Initialize
weave.init(project_name="my-project")

# Track operations
@weave.op()
def my_function(input: str) -> str:
    return f"processed: {input}"
```

---

## Core API

### `weave.init()`

Initialize Weave for tracking.

**Signature:**
```python
def weave.init(
    project_name: str,
    entity: str | None = None,
    mode: str | None = None,
) -> None
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `project_name` | `str` | Project name (required) |
| `entity` | `str \| None` | Team/workspace name (Cloud only) |
| `mode` | `str \| None` | `"local"`, `"cloud"`, or `"readonly"` |

**Example:**
```python
# Local mode
weave.init(project_name="sit-copilot")

# Cloud mode
weave.init(
    project_name="sit-copilot",
    entity="my-team"
)

# Readonly (no writes)
weave.init(project_name="sit-copilot", mode="readonly")
```

**Environment Variables:**
| Variable | Description |
|----------|-------------|
| `WANDB_API_KEY` | API key for Cloud mode |
| `WANDB_ENTITY` | Default entity/team |
| `WEAVE_MODE` | Force mode (local/cloud) |

---

### `@weave.op()` Decorator

Mark a function for automatic tracking.

**Signature:**
```python
def weave.op(
    name: str | None = None,
    resolve_types: bool = True,
    sample_rate: float = 1.0,
)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str \| None` | `function.__name__` | Operation name |
| `resolve_types` | `bool` | `True` | Auto-resolve type hints |
| `sample_rate` | `float` | `1.0` | Sampling rate (0-1) |

**Examples:**
```python
# Basic usage
@weave.op()
async def fetch_data(source: str) -> dict:
    return {"source": source}

# Custom name
@weave.op(name="custom.operation")
def process(x: int) -> int:
    return x * 2

# Sampling (track 10% of calls)
@weave.op(sample_rate=0.1)
async def high_traffic_handler():
    pass
```

---

### `weave.publish()`

Manually publish data to Weave.

**Signature:**
```python
def weave.publish(data: dict, *, name: str | None = None) -> None
```

**Example:**
```python
@weave.op()
async def tracked_operation():
    result = await some_async_work()
    
    weave.publish({
        "result": result,
        "latency_ms": elapsed_ms,
        "custom_metric": custom_value
    })
    
    return result
```

---

### `weave.attributes_context()`

Set contextual attributes for all child operations.

**Signature:**
```python
@contextlib.contextmanager
def weave.attributes_context(attributes: dict)
```

**Example:**
```python
from fastapi import Request

@app.middleware("http")
async def weave_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID")
    
    with weave.attributes_context({
        "trace_id": trace_id,
        "path": request.url.path,
        "method": request.method
    }):
        response = await call_next(request)
    
    return response
```

---

## Type Tracking

Weave automatically tracks function signatures and return types.

```python
from typing import TypedDict

class QueryInput(TypedDict):
    text: str
    top_k: int

class QueryResult(TypedDict):
    results: list[str]
    count: int

@weave.op()
async def semantic_search(input: QueryInput) -> QueryResult:
    # Weave captures the TypedDict structure
    results = await search(input["text"], input["top_k"])
    return {"results": results, "count": len(results)}
```

---

## Object Tracking

Weave automatically serializes complex objects.

```python
from pydantic import BaseModel

class Document(BaseModel):
    id: str
    content: str
    metadata: dict

@weave.op()
def process_document(doc: Document) -> Document:
    # Pydantic models are automatically tracked
    return Document(
        id=doc.id,
        content=doc.content.upper(),
        metadata=doc.metadata
    )
```

---

## Async Support

Weave fully supports async/await.

```python
import asyncio

@weave.op()
async def async_operation(x: int) -> int:
    await asyncio.sleep(0.1)
    return x * 2

@weave.op()
async def parallel_process(items: list[int]) -> list[int]:
    # Each coroutine is tracked separately
    tasks = [async_operation(x) for x in items]
    return await asyncio.gather(*tasks)
```

---

## Integration with FastAPI

### Middleware Pattern

```python
from fastapi import FastAPI, Request
import weave

app = FastAPI()

@app.on_event("startup")
async def startup():
    weave.init(project_name="fastapi-app")

@app.middleware("http")
async def weave_middleware(request: Request, call_next):
    with weave.attributes_context({
        "path": request.url.path,
        "method": request.method
    }):
        response = await call_next(request)
    return response
```

### Dependency Pattern

```python
from fastapi import Depends

def get_weave_client():
    # Return weave module or custom wrapper
    return weave

@app.post("/process")
async def process_endpoint(
    data: dict,
    weave_client=Depends(get_weave_client)
):
    @weave_client.op()
    async def inner_process():
        return {"processed": data}
    
    return await inner_process()
```

---

## Error Handling

Weave errors should never break your application.

```python
import logging

logger = logging.getLogger(__name__)

@weave.op()
async def safe_operation():
    try:
        result = await risky_operation()
        return result
    except Exception as e:
        # Log but don't raise
        logger.warning(f"Operation failed: {e}")
        # Weave still tracks the failure
        raise  # Or return a fallback value
```

---

## Configuration

### Settings Schema

```python
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal

class WeaveSettings(BaseSettings):
    """Weave configuration."""
    
    # Basic
    enabled: bool = Field(default=False)
    project: str = Field(default="sit-copilot")
    entity: str = Field(default="")
    
    # Mode
    mode: Literal["local", "cloud", "readonly"] = "local"
    
    # Cloud auth
    api_key: str = Field(default="", alias="wandb_api_key")
    
    # Sampling
    sample_rate: float = Field(default=1.0, ge=0, le=1)
    
    # Performance
    offline_mode: bool = Field(default=False)
    
    class Config:
        env_prefix = "WEAVE_"
        extra = "ignore"
```

---

## Testing Patterns

### Mock Weave in Tests

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def weave_disabled():
    """Disable Weave during tests."""
    with patch.dict("os.environ", {"WEAVE_ENABLED": "false"}):
        yield

@pytest.mark.asyncio
async def test_operation(weave_disabled):
    # Weave is disabled, no side effects
    result = await my_operation()
    assert result == expected
```

### Noop Implementation

```python
class NoopWeave:
    """No-op Weave implementation for testing."""
    
    def op(self, **kwargs):
        def decorator(fn):
            return fn  # Return function unchanged
        return decorator
    
    def init(self, **kwargs):
        pass
    
    def publish(self, **kwargs):
        pass
    
    def attributes_context(self, attrs):
        from contextlib import contextmanager
        
        @contextmanager
        def noop_context():
            yield
        return noop_context()

# Use in tests
noop_weave = NoopWeave()
```

---

## Best Practices

### 1. Always Use Async

```python
# Bad: Blocking call
@weave.op()
def blocking_call():
    time.sleep(1)  # Blocks event loop

# Good: Async call
@weave.op()
async def async_call():
    await asyncio.sleep(1)  # Non-blocking
```

### 2. Error Isolation

```python
# Bad: Weave error breaks app
@weave.op()
async def risky_operation():
    result = await api_call()
    weave.publish(result)  # Might fail
    return result

# Good: Isolated Weave calls
@weave.op()
async def safe_operation():
    result = await api_call()
    try:
        weave.publish(result)
    except Exception:
        pass  # Log and ignore
    return result
```

### 3. Context Propagation

```python
# Bad: Missing context
@weave.op()
async def orphan_operation():
    return await work()  # No trace context

# Good: With context
with weave.attributes_context({"user_id": user.id}):
    await orphan_operation()  # Has user context
```

### 4. Sampling for High Traffic

```python
# Bad: Track everything
@weave.op()
async def high_traffic_handler():
    pass  # Called 1000x/sec = too much data

# Good: Sample
@weave.op(sample_rate=0.01)  # 1% sampling
async def high_traffic_handler():
    pass
```

---

## Constraints and Limitations

| Constraint | Details |
|------------|---------|
| **Python Version** | 3.8+ required |
| **Async Support** | Requires `asyncio` event loop |
| **Serialization** | Custom objects need `__dict__` or `dataclass` |
| **Network** | Cloud mode requires HTTPS to `api.wandb.ai` |
| **Data Size** | Large payloads may be truncated |
| **Thread Safety** | Use separate Weave clients per thread |

---

## Common Issues and Solutions

### Issue: "GEMINI_API_KEY not set"

**Solution:** This is a Gemini CLI error, not Weave. For Weave, set `WANDB_API_KEY`.

```bash
export WANDB_API_KEY="your-key"
```

### Issue: Blocking the event loop

**Solution:** Always use async Weave operations in FastAPI.

```python
# Bad: sync in async context
@weave.op()
def sync_in_async():
    return blocking_io()

# Good: native async
@weave.op()
async def native_async():
    return await async_io()
```

### Issue: Missing trace context

**Solution:** Use middleware to set global context.

```python
@app.middleware("http")
async def weave_context_middleware(request: Request, call_next):
    with weave.attributes_context({
        "request_id": generate_id(),
        "user_id": get_user_id(request)
    }):
        return await call_next(request)
```

---

## Version Compatibility

| Weave Version | Python | FastAPI | Notes |
|---------------|--------|---------|-------|
| 0.50+ | 3.8-3.12 | 0.100+ | Latest |
| 0.40-0.49 | 3.8-3.11 | 0.90+ | Stable |
| <0.40 | 3.8-3.10 | 0.85+ | Legacy |

---

## Further Reading

- **Official Docs**: https://docs.wandb.ai/guides/weave
- **GitHub**: https://github.com/wandb/weave
- **Discord**: https://wandb.me/community
- **Status**: https://status.wandb.ai

