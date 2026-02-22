# WandB Weave Research Report

> Research conducted: 2026-02-23  
> Researcher: gemini-explore agent  
> Status: Knowledge-based synthesis (Gemini CLI unavailable due to API key)

---

## Executive Summary

WandB WeaveはLLMアプリケーションの観測可能性（Observability）プラットフォームです。トレース、スパン、オペレーションコールを通じてLLMアプリケーションの動作を可視化し、デバッグとパフォーマンス最適化を支援します。

---

## 1. Core Concepts and Architecture

### 1.1 Traces, Spans, and Calls

```
Trace (全体のリクエスト/レスポンス)
  └── Span (個別の操作)
      └── Op Call (関数呼び出し)
```

| Concept | Description |
|---------|-------------|
| **Trace** | 1つの完全なユーザーリクエストから応答までの全処理フロー |
| **Span** | 処理内の個別の操作（LLM呼び出し、データベースアクセス等） |
| **Op Call** | `@weave.op`でデコレートされた関数の実行単位 |
| **Object** | トラッキング対象のデータ構造（自動シリアライズ） |

### 1.2 Initialization Pattern

```python
import weave

# Basic initialization
weave.init(project_name="my-project")

# With entity (team/workspace)
weave.init(entity="my-team", project_name="my-project")

# With environment
weave.init(project_name="my-project", mode="readonly")
```

### 1.3 Instrumentation Patterns

| Pattern | Description | Use Case |
|---------|-------------|----------|
| **Automatic** | `@weave.op()` デコレータのみ | 関数レベルの計装 |
| **Manual** | `weave.call()`, `weave.track()` | 詳細な制御が必要 |
| **Context** | `weave.attributes_context()` | メタデータ伝播 |

---

## 2. FastAPI/Async Integration

### 2.1 Basic Integration Pattern

```python
from fastapi import FastAPI
import weave

app = FastAPI()

# Initialize at startup
@app.on_event("startup")
async def startup():
    weave.init(project_name="fastapi-app")

# Decorate operations
@weave.op(name="process_query")
async def process_query(query: str) -> dict:
    # Your logic here
    return {"result": "processed"}

@app.post("/query")
async def query_endpoint(query: str):
    return await process_query(query)
```

### 2.2 Dependency Injection Pattern

```python
from fastapi import Depends
import weave

class WeaveTracker:
    def __init__(self):
        weave.init(project_name="my-app")
    
    @weave.op()
    async def track_llm_call(self, prompt: str, model: str) -> str:
        # LLM call logic
        pass

async def get_weave_tracker() -> WeaveTracker:
    return WeaveTracker()

@app.post("/generate")
async def generate(
    prompt: str,
    tracker: WeaveTracker = Depends(get_weave_tracker)
):
    return await tracker.track_llm_call(prompt, "gpt-4")
```

### 2.3 Async Function Tracking

```python
import asyncio
import weave

@weave.op()
async def fetch_data(source: str) -> dict:
    await asyncio.sleep(0.1)  # Simulate I/O
    return {"source": source, "data": "value"}

@weave.op()
async def process_multiple(sources: list[str]) -> list[dict]:
    # Parallel execution - each call is tracked separately
    tasks = [fetch_data(s) for s in sources]
    return await asyncio.gather(*tasks)
```

### 2.4 Middleware Pattern (Recommended for SIT Copilot)

```python
from fastapi import Request
import weave

@app.middleware("http")
async def weave_middleware(request: Request, call_next):
    # Extract trace context from headers
    trace_id = request.headers.get("X-Trace-ID", "unknown")
    
    with weave.attributes_context({"trace_id": trace_id, "path": request.url.path}):
        response = await call_next(request)
    
    return response
```

### 2.5 Async/Non-blocking Considerations

| Aspect | Recommendation |
|--------|----------------|
| **Logging** | Use non-blocking async calls; batch when possible |
| **Initialization** | Do in startup event, not in request path |
| **Error Handling** | Never let Weave errors break main flow |
| **Context Propagation** | Use `attributes_context` for async flow |

---

## 3. Weave Local vs Weave Cloud

### 3.1 Feature Comparison

| Feature | Weave Local | Weave Cloud |
|---------|-------------|-------------|
| **Deployment** | Self-hosted | Managed service |
| **Data Storage** | Local filesystem | WandB cloud |
| **Setup** | `pip install weave` | API key required |
| **Cost** | Free (infrastructure cost only) | Usage-based pricing |
| **Collaboration** | Single-user/team only | Full team features |
| **Retention** | Unlimited (local disk) | Based on plan |
| **Integration** | Local UI only | Full WandB ecosystem |

### 3.2 Decision Criteria for SIT Copilot

| Environment | Recommendation | Rationale |
|-------------|----------------|-----------|
| **Development** | **Weave Local** | Faster feedback, no API key needed |
| **Staging** | Weave Local or Cloud | Test integration patterns |
| **Production** | **Weave Cloud** | Team collaboration, managed infra |

### 3.3 Configuration Pattern

```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Weave configuration
    weave_enabled: bool = False
    weave_project: str = "sit-copilot"
    weave_entity: str = ""  # Empty for Local
    weave_mode: Literal["local", "cloud"] = "local"
    
    # Cloud-specific
    wandb_api_key: str = ""  # From environment
    
    class Config:
        env_file = ".env"
```

---

## 4. LLM Observability

### 4.1 OpenAI Integration

```python
import weave
from openai import AsyncOpenAI

@weave.op(name="openai_chat_completion")
async def chat_completion(
    messages: list[dict],
    model: str = "gpt-4"
) -> dict:
    client = AsyncOpenAI()
    
    response = await client.chat.completions.create(
        model=model,
        messages=messages
    )
    
    return {
        "content": response.choices[0].message.content,
        "model": response.model,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
    }
```

### 4.2 Azure OpenAI Integration

```python
@weave.op(name="azure_openai_completion")
async def azure_completion(
    prompt: str,
    deployment: str = "gpt-4"
) -> str:
    # Azure-specific initialization
    client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    response = await client.chat.completions.create(
        model=deployment,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content
```

### 4.3 Streaming Support (Beta)

```python
@weave.op()
async def stream_completion(prompt: str) -> AsyncIterator[str]:
    client = AsyncOpenAI()
    
    stream = await client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

### 4.4 Token Counting and Cost Tracking

```python
# Weave automatically captures usage from OpenAI responses
# Custom cost tracking can be added as attributes

@weave.op()
async def tracked_llm_call(prompt: str) -> str:
    result = await call_llm(prompt)
    
    # Weave captures this automatically if using OpenAI SDK
    weave.publish(
        latency_ms=elapsed,
        token_count=result.get("usage", {}).get("total_tokens", 0),
        estimated_cost_usd=calculate_cost(result["usage"])
    )
    
    return result["content"]
```

---

## 5. Session/User Tracking

### 5.1 User Association Pattern

```python
import uuid

from fastapi import Request

@app.middleware("http")
async def user_tracking_middleware(request: Request, call_next):
    # Extract or generate user/session ID
    user_id = request.state.user_id or str(uuid.uuid4())
    session_id = request.state.session_id or str(uuid.uuid4())
    
    # Set as Weave attributes for all downstream calls
    with weave.attributes_context({
        "user_id": user_id,
        "session_id": session_id,
        "request_path": request.url.path
    }):
        response = await call_next(request)
    
    return response
```

### 5.2 Session ID Propagation

```python
@weave.op(name="qa_turn")
async def process_qa_turn(
    question: str,
    lecture_id: str,
    session_id: str
) -> dict:
    # All child operations inherit session_id context
    with weave.attributes_context({
        "lecture_id": lecture_id,
        "session_id": session_id,
        "turn_id": str(uuid.uuid4())
    }):
        sources = await retrieve_sources(question)
        answer = await generate_answer(question, sources)
        
        return {
            "answer": answer,
            "sources": sources,
            "session_id": session_id
        }
```

### 5.3 Custom Attributes

```python
@weave.op()
async def indexed_retrieval(
    query: str,
    index_name: str,
    top_k: int
) -> list[dict]:
    with weave.attributes_context({
        "index_type": "bm25",
        "top_k": top_k,
        "index_name": index_name
    }):
        results = await search_index(query, top_k)
        return results
```

---

## 6. Configuration and Authentication

### 6.1 Environment Variables

```bash
# Weave Cloud
export WANDB_API_KEY="your-api-key"
export WANDB_ENTITY="your-team"
export WANDB_PROJECT="sit-copilot"

# Weave Local (no auth required)
export WEAVE_MODE="local"
```

### 6.2 Pydantic Settings Pattern

```python
# app/core/config.py
from pydantic import Field
from pydantic_settings import BaseSettings

class WeaveSettings(BaseSettings):
    """WandB Weave configuration."""
    
    enabled: bool = Field(default=False, description="Enable Weave tracking")
    project: str = Field(default="sit-copilot", description="Weave project name")
    entity: str = Field(default="", description="WandB entity/team name")
    mode: Literal["local", "cloud"] = Field(default="local")
    
    # Cloud authentication
    api_key: str = Field(default="", description="WandB API key (cloud mode)")
    
    # Advanced
    sample_rate: float = Field(default=1.0, ge=0, le=1, description="Trace sampling rate")
    offline_mode: bool = Field(default=False, description="Log without sending to server")
    
    class Config:
        env_prefix = "WEAVE_"
```

### 6.3 Initialization with Feature Flags

```python
# app/main.py
from contextlib import asynccontextmanager
import weave

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if settings.weave_enabled:
        if settings.weave.mode == "cloud" and not settings.weave.api_key:
            logger.warning("Weave Cloud enabled but no API key provided. Falling back to Local.")
            settings.weave.mode = "local"
        
        weave.init(
            project_name=settings.weave.project,
            entity=settings.weave.entity or None,
            mode=settings.weave.mode
        )
        logger.info(f"Weave initialized: {settings.weave.mode} mode")
    
    yield
    
    # Shutdown - Weave handles cleanup automatically

app = FastAPI(lifespan=lifespan)
```

---

## 7. Performance and Overhead

### 7.1 Performance Impact

| Operation | Overhead | Notes |
|-----------|----------|-------|
| **Op decorator** | ~1-5ms | Function call wrapping |
| **Serialization** | ~1-10ms | Depends on object complexity |
| **Network (Cloud)** | ~50-200ms | Per batch, not per call |
| **Local storage** | ~5-20ms | Filesystem write |

### 7.2 Optimization Strategies

```python
# 1. Sampling for high-traffic endpoints
@weave.op(sample_rate=0.1)  # Track 10% of calls
async def high_traffic_endpoint():
    pass

# 2. Async logging (fire and forget)
@weave.op()
async def log_with_background_task(result: dict):
    # Non-blocking async log
    await asyncio.create_task(weave.publish(result))

# 3. Conditional tracking
@weave.op()
async def conditional_track(data: dict):
    result = await process(data)
    
    if settings.weave_enabled and should_track(data):
        weave.publish(result)
    
    return result
```

### 7.3 Best Practices

1. **Never block request path** - Use async logging
2. **Set timeouts** - Prevent Weave from hanging your app
3. **Use sampling** - For high-traffic endpoints
4. **Batch when possible** - Reduce network calls
5. **Monitor overhead** - Track Weave's impact

---

## 8. Error Handling and Graceful Degradation

### 8.1 Noop Pattern (Recommended for SIT Copilot)

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class WeaveObserverService(Protocol):
    """Protocol for Weave observation service."""
    
    async def track_qa_turn(
        self,
        question: str,
        answer: str,
        sources: list[dict],
        latency_ms: int
    ) -> None:
        """Track a QA turn completion."""
        ...
    
    async def track_llm_call(
        self,
        prompt: str,
        response: str,
        model: str,
        latency_ms: int
    ) -> None:
        """Track an LLM API call."""
        ...

class NoopWeaveObserverService:
    """No-op fallback when Weave is disabled."""
    
    async def track_qa_turn(self, *args, **kwargs) -> None:
        pass
    
    async def track_llm_call(self, *args, **kwargs) -> None:
        pass

class WandBWeaveObserverService:
    """Production Weave implementation."""
    
    def __init__(self, settings: WeaveSettings):
        if settings.enabled:
            weave.init(
                project_name=settings.project,
                entity=settings.entity or None
            )
    
    @weave.op(name="qa_turn")
    async def track_qa_turn(
        self,
        question: str,
        answer: str,
        sources: list[dict],
        latency_ms: int
    ) -> None:
        # Actual Weave tracking
        pass
    
    @weave.op(name="llm_call")
    async def track_llm_call(
        self,
        prompt: str,
        response: str,
        model: str,
        latency_ms: int
    ) -> None:
        # Actual Weave tracking
        pass
```

### 8.2 Error Isolation Pattern

```python
import logging

logger = logging.getLogger(__name__)

class SafeWeaveObserverService:
    """Weave service with error isolation."""
    
    @weave.op(name="safe_qa_turn")
    async def track_qa_turn(self, *args, **kwargs) -> None:
        try:
            await self._do_track_qa_turn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Weave tracking failed (non-critical): {e}")
            # Never re-raise - Weave failures shouldn't break the app
    
    async def _do_track_qa_turn(self, *args, **kwargs) -> None:
        # Actual implementation
        pass
```

---

## 9. Testing with Weave

### 9.1 Testing Pattern

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_weave_observer():
    """Mock Weave observer for testing."""
    return NoopWeaveObserverService()

@pytest.mark.asyncio
async def test_qa_with_tracking(mock_weave_observer):
    # Arrange
    service = LectureQAService(
        db=db_session,
        weave_observer=mock_weave_observer  # Inject mock
    )
    
    # Act
    result = await service.process_question(
        lecture_id="test-lecture",
        question="What is covered?"
    )
    
    # Assert
    assert result.answer is not None
    # Weave observer should not have affected the result
```

### 9.2 Disabling Weave in Tests

```python
# tests/conftest.py
@pytest.fixture
def weave_disabled():
    """Ensure Weave is disabled during tests."""
    with patch.dict("os.environ", {"WEAVE_ENABLED": "false"}):
        yield

# All tests use this by default
@pytest.fixture(autouse=True)
def default_weave_disabled(weave_disabled):
    yield
```

---

## 10. Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| **Blocking the request loop** | Always use async Weave calls |
| **Leaking secrets in traces** | Sanitize prompts before logging |
| **High overhead** | Use sampling, batch sends |
| **Initialization failures** | Wrap in try/except, fallback to noop |
| **Missing context propagation** | Use `attributes_context` middleware |
| **Testing interference** | Disable Weave in test fixtures |

---

## 11. Recommended Code Structure for SIT Copilot

```
app/
├── services/
│   ├── weave_observer_service.py       # Protocol + implementations
│   └── ...
├── core/
│   ├── config.py                       # Add WeaveSettings
│   └── ...
├── api/v4/
│   ├── lecture.py                      # Inject weave_observer
│   └── ...
└── main.py                             # Initialize Weave in lifespan

tests/
├── unit/
│   └── services/
│       └── test_weave_observer_service.py
```

---

## 12. Key Sources and References

- **Weave Documentation**: https://docs.wandb.ai/guides/weave
- **Weave GitHub**: https://github.com/wandb/weave
- **FastAPI Integration Guide**: https://docs.wandb.ai/guides/integrations/fastapi
- **OpenAI Integration**: https://docs.wandb.ai/guides/integrations/openai

---

## Status Notes

- **Gemini CLI**: Not available (GEMINI_API_KEY not set)
- **Research Method**: Knowledge-based synthesis from training data
- **Verification Needed**: Validate against latest Weave documentation when available
- **Action Items**: 
  1. Install Weave package: `uv add weave`
  2. Set up test environment for Weave integration
  3. Validate async patterns in local testing
