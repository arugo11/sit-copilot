# F4 QA Test Completion - Testing Research

## Overview

Research document for improving test coverage of F4 Lecture QA services:
- `app/services/lecture_bm25_store.py` (0% → 80%+)
- `app/services/lecture_verifier_service.py` (49% → 80%+)
- `app/services/lecture_followup_service.py` (35% → 80%+)

---

## 1. rank-bm25 Testing Patterns

### Library Characteristics
- **rank-bm25** is NOT thread-safe
- Pure Python implementation of BM25 ranking algorithm
- CPU-bound operations → use `asyncio.to_thread()` for async wrapper
- No incremental updates → rebuild entire index when new chunks added

### Testing Constraints
```python
# rank-bm25 creates stateful indices that are NOT thread-safe
from rank_bm25 import BM25Okapi

# Tokenized corpus must be pre-computed
corpus = ["hello world", "foo bar"]
tokenized_corpus = [doc.split() for doc in corpus]
bm25 = BM25Okapi(tokenized_corpus)  # Creates internal state
```

### Testing Best Practices
1. **Mock BM25 operations** for unit tests (avoid actual computation)
2. **Test tokenization logic** separately
3. **Use FakeBM25Index** pattern (similar to existing FakeAzureSearchService)
4. **Test thread-safety** using concurrent `asyncio.gather()` calls

### Recommended Mock Pattern
```python
class FakeBM25Index:
    """Fake BM25 index for testing without actual rank-bm25 dependency."""
    
    def __init__(self, scores: list[float] | None = None):
        self._scores = scores or []
        self.call_count = 0
    
    def get_scores(self, query: list[str]) -> list[float]:
        self.call_count += 1
        return self._scores
```

---

## 2. pytest-asyncio Best Practices

### Configuration (Already Set in pyproject.toml)
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # No need for explicit @pytest.mark.asyncio
```

### Key Patterns from Research

#### Async Fixtures
```python
import pytest

@pytest.fixture
async def async_resource():
    resource = await setup_async_resource()
    yield resource
    await teardown_async_resource(resource)
```

#### Testing Async Context Managers
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_async_context_manager():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    
    async with mock_session as session:
        # Test code here
        pass
```

#### Parametrized Async Tests
```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (3, 4),
])
@pytest.mark.asyncio
async def test_async_parametrized(input, expected):
    result = await async_add(input, 1)
    assert result == expected
```

### Common Pitfalls to Avoid
1. **Don't mix** synchronous and asynchronous test styles in the same file
2. **Always await** async operations in tests
3. **Ensure proper cleanup** of async resources (use yield in fixtures)
4. **Don't forget** `@pytest.mark.asyncio` if `asyncio_mode != "auto"`

---

## 3. Mocking Azure OpenAI API Calls

### Key Pattern: Use AsyncMock for HTTP Operations

The services use `urllib.request.urlopen` wrapped in `asyncio.to_thread()`. Mock the sync function:

```python
from unittest.mock import patch, AsyncMock
import json

@pytest.fixture
def mock_openai_response():
    """Mock successful Azure OpenAI response."""
    return {
        "choices": [{
            "message": {
                "content": "test response"
            }
        }]
    }

@pytest.mark.asyncio
async def test_azure_openai_call(mock_openai_response):
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )
    
    # Mock the synchronous urlopen call
    with patch('app.services.lecture_verifier_service.urlopen') as mock_urlopen:
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.read.return_value = json.dumps(mock_openai_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = await service.verify(
            question="test",
            answer="test answer",
            sources=[],
        )
        
        mock_urlopen.assert_called_once()
```

### Mocking Different Response Scenarios

#### 1. HTTP Error (4xx/5xx)
```python
from urllib.error import HTTPError

@pytest.mark.asyncio
async def test_http_error_fallback():
    with patch('app.services.lecture_verifier_service.urlopen') as mock_urlopen:
        mock_urlopen.side_effect = HTTPError(
            url="https://test.openai.azure.com/",
            code=429,
            msg="Rate limited",
            hdrs={},
            fp=None
        )
        
        # Should raise LectureVerifierError or use local fallback
        with pytest.raises(LectureVerifierError):
            await service.verify(...)
```

#### 2. Network Error
```python
from urllib.error import URLError

@pytest.mark.asyncio
async def test_network_error():
    with patch('app.services.lecture_verifier_service.urlopen') as mock_urlopen:
        mock_urlopen.side_effect = URLError("Network error")
        
        with pytest.raises(LectureVerifierError):
            await service.verify(...)
```

#### 3. JSON Parse Error
```python
@pytest.mark.asyncio
async def test_json_parse_error():
    with patch('app.services.lecture_verifier_service.urlopen') as mock_urlopen:
        mock_response = AsyncMock()
        mock_response.read.return_value = b"invalid json"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with pytest.raises(LectureVerifierError):
            await service.verify(...)
```

### Testing Without Azure OpenAI (Local Fallback)
```python
@pytest.mark.asyncio
async def test_local_verify_fallback():
    service = AzureOpenAILectureVerifierService(
        api_key="",  # Empty → local fallback
        endpoint="",
    )
    
    result = await service.verify(
        question="test",
        answer="test answer",
        sources=[LectureSource(text="test answer", ...)],
    )
    
    assert result.passed is True  # Local verify should match
```

---

## 4. Testing Thread-Safe Async Code (asyncio.Lock)

### Key Pattern: Test Concurrent Access

```python
import asyncio
import pytest

@pytest.mark.asyncio
async def test_concurrent_get_operations():
    """Concurrent gets should not raise exceptions."""
    store = LectureBM25Store()
    
    # Setup index
    await store.put(
        session_id="test-session",
        chunks=[{"id": "1", "text": "test"}],
        tokenized_corpus=[["test"]],
        index_version="v1",
    )
    
    # Concurrent reads
    results = await asyncio.gather(
        store.get("test-session"),
        store.get("test-session"),
        store.get("test-session"),
    )
    
    assert all(r is not None for r in results)

@pytest.mark.asyncio
async def test_concurrent_put_operations():
    """Concurrent puts should be serialized by lock."""
    store = LectureBM25Store()
    
    # Concurrent writes to same session
    await asyncio.gather(
        store.put("session-1", [], [], "v1"),
        store.put("session-1", [], [], "v2"),
        store.put("session-1", [], [], "v3"),
    )
    
    # Last write should win (or all complete)
    index = await store.get("session-1")
    assert index is not None
    assert index.index_version == "v3"  # Deterministic ordering
```

### Testing Lock State (Internal Testing)
```python
@pytest.mark.asyncio
async def test_lock_acquisition():
    """Verify that lock prevents race conditions."""
    store = LectureBM25Store()
    
    lock_acquired = []
    
    async def task1():
        lock = await store.acquire_lock("test-session")
        async with lock:
            lock_acquired.append(1)
            await asyncio.sleep(0.1)  # Hold lock
            lock_acquired.append(2)
    
    async def task2():
        await asyncio.sleep(0.05)  # Start after task1 acquires lock
        lock = await store.acquire_lock("test-session")
        async with lock:
            lock_acquired.append(3)
    
    await asyncio.gather(task1(), task2())
    
    # Should be 1, 2, 3 (not 1, 3, 2)
    assert lock_acquired == [1, 2, 3]
```

---

## 5. SQLAlchemy AsyncSession Mocking Patterns

### Pattern 1: AsyncMock for Session Operations

```python
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture
def mock_db_session():
    """Mock AsyncSession for testing."""
    session = AsyncMock(spec=AsyncSession)
    
    # Mock execute() to return a result with scalars()
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result
    
    return session
```

### Pattern 2: Fake AsyncSession with In-Memory Data

```python
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

class FakeAsyncSession:
    """In-memory fake AsyncSession for unit tests."""
    
    def __init__(self, data: list[Any] | None = None):
        self._data = data or []
        self._execute_calls = []
    
    async def execute(self, statement):
        self._execute_calls.append(statement)
        # Return fake result
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = self._data
        return mock_result
    
    def get_execute_calls(self):
        """Return list of executed statements for assertions."""
        return self._execute_calls

@pytest.mark.asyncio
async def test_followup_loads_history():
    fake_db = FakeAsyncSession(data=[
        QATurn(question="Q1", answer="A1", ...),
        QATurn(question="Q2", answer="A2", ...),
    ])
    
    service = SqlAlchemyLectureFollowupService(
        db=fake_db,
        openai_api_key="",  # Use simple rewrite
    )
    
    result = await service.resolve_query(
        session_id="test-session",
        user_id="user-1",
        question="それについて詳しく",
    )
    
    # Verify history was loaded
    assert len(fake_db.get_execute_calls()) > 0
    assert "それは" in result.standalone_query
```

### Pattern 3: Real In-Memory Database (Already in conftest.py)

```python
@pytest.mark.asyncio
async def test_followup_with_real_db(db_session: AsyncSession):
    """Test with real in-memory SQLite."""
    # Setup test data
    turn = QATurn(
        session_id="test-session",
        feature="lecture_qa",
        question="最初の質問",
        answer="最初の回答",
        created_at=datetime.now(UTC),
    )
    db_session.add(turn)
    await db_session.commit()
    
    # Test service
    service = SqlAlchemyLectureFollowupService(
        db=db_session,
        openai_api_key="",
    )
    
    result = await service.resolve_query(
        session_id="test-session",
        user_id="user-1",
        question="それについて詳しく",
    )
    
    assert "最初の質問" in result.standalone_query or "それ" in result.standalone_query
```

---

## 6. Test File Structure Recommendations

### For lecture_bm25_store.py
```python
"""Tests for LectureBM25Store."""

import asyncio
import pytest
from app.services.lecture_bm25_store import LectureBM25Store, LectureBM25Index

@pytest.mark.asyncio
async def test_put_and_get_index():
    ...

@pytest.mark.asyncio
async def test_concurrent_access():
    ...

@pytest.mark.asyncio
async def test_delete_index():
    ...

@pytest.mark.asyncio
async def test_has_index():
    ...

@pytest.mark.asyncio
async def test_acquire_lock():
    ...

@pytest.mark.asyncio
async def test_get_nonexistent_returns_none():
    ...

# Edge cases
@pytest.mark.asyncio
async def test_put_replaces_existing_index():
    ...

@pytest.mark.asyncio
async def test_chunk_map_lookup():
    ...
```

### For lecture_verifier_service.py
```python
"""Tests for AzureOpenAILectureVerifierService."""

import pytest
from unittest.mock import patch
from app.services.lecture_verifier_service import (
    AzureOpenAILectureVerifierService,
    LectureVerificationResult,
)

# Existing tests
def test_parse_verification_result_handles_string_false_as_false():
    ...

def test_parse_verification_result_rejects_non_boolean_passed():
    ...

# New tests needed
@pytest.mark.asyncio
async def test_verify_with_no_sources():
    ...

@pytest.mark.asyncio
async def test_verify_with_azure_openai_success():
    ...

@pytest.mark.asyncio
async def test_verify_with_http_error():
    ...

@pytest.mark.asyncio
async def test_verify_with_network_error():
    ...

@pytest.mark.asyncio
async def test_local_verify_with_matching_content():
    ...

@pytest.mark.asyncio
async def test_local_verify_with_no_match():
    ...

@pytest.mark.asyncio
async def test_repair_answer_with_sources():
    ...

@pytest.mark.asyncio
async def test_repair_answer_returns_none_on_failure():
    ...

@pytest.mark.asyncio
async def test_extract_content_from_list_format():
    ...

# Edge cases
@pytest.mark.asyncio
async def test_parse_verification_result_malformed_json():
    ...

def test_normalize_unsupported_claims_filters_non_strings():
    ...

def test_parse_passed_flag_various_types():
    ...
```

### For lecture_followup_service.py
```python
"""Tests for SqlAlchemyLectureFollowupService."""

import pytest
from app.services.lecture_followup_service import (
    SqlAlchemyLectureFollowupService,
    FollowupResolution,
)

@pytest.mark.asyncio
async def test_resolve_query_with_empty_history():
    ...

@pytest.mark.asyncio
async def test_resolve_query_with_history():
    ...

@pytest.mark.asyncio
async def test_resolve_query_with_pronoun_prefix():
    ...

@pytest.mark.asyncio
async def test_simple_rewrite_no_history():
    ...

@pytest.mark.asyncio
async def test_simple_rewrite_with_pronoun():
    ...

@pytest.mark.asyncio
async def test_simple_rewrite_unknown_prefix():
    ...

@pytest.mark.asyncio
async def test_azure_openai_rewrite_success():
    ...

@pytest.mark.asyncio
async def test_azure_openai_rewrite_falls_back_to_simple():
    ...

def test_format_history_empty():
    ...

def test_format_history_with_turns():
    ...

def test_is_azure_openai_ready_missing_config():
    ...

def test_is_azure_openai_ready_invalid_endpoint():
    ...

@pytest.mark.asyncio
async def test_extract_content_various_formats():
    ...

# Edge cases
@pytest.mark.asyncio
async def test_load_history_empty_database():
    ...

@pytest.mark.asyncio
async def test_build_rewrite_prompt_structure():
    ...
```

---

## 7. Coverage Goals

### lecture_bm25_store.py (0% → 80%+)
- [x] Public API: `get`, `put`, `delete`, `acquire_lock`, `has_index`
- [x] Concurrent access patterns
- [x] Edge cases: nonexistent sessions, replacement
- [x] Internal: chunk_map lookup, lock management

### lecture_verifier_service.py (49% → 80%+)
- [x] `verify()` with various source scenarios
- [x] `repair_answer()` with various outcomes
- [x] Local fallback paths (`_local_verify`, `_local_repair_answer`)
- [x] Error handling: HTTP, network, parse errors
- [x] Helper methods: `_extract_content`, `_normalize_unsupported_claims`, `_parse_passed_flag`

### lecture_followup_service.py (35% → 80%+)
- [x] `resolve_query()` with empty/non-empty history
- [x] Simple rewrite fallback paths
- [x] Azure OpenAI rewrite + error handling
- [x] Helper methods: `_format_history`, `_simple_rewrite`, `_is_azure_openai_ready`
- [x] `_extract_content()` for various response formats

---

## 8. Sources

- **pytest-asyncio**: https://pypi.org/project/pytest-asyncio/
- **pytest-asyncio Best Practices** (CSDN, 2025): https://blog.csdn.net/gitblog_00136/article/details/148962176
- **AsyncMock for LLM Testing** (CSDN, 2025): https://m.blog.csdn.net/gitblog_00861/article/details/150962176
- **Async Context Manager Mocking** (DZone): https://dzone.com/articles/mastering-async-context-manager-mocking-in-python
- **Azure OpenAI Mocking** (Microsoft Learn): https://learn.microsoft.com/en-us/microsoft-cloud/dev/dev-proxy/how-to/simulate-azure-openai
- **SQLAlchemy Async Testing** (CSDN, 2025): https://blog.csdn.net/linsuiyuan123/article/details/146442690
- **asyncio.Lock Testing** (General Python patterns): Web search results on thread-safe async code
