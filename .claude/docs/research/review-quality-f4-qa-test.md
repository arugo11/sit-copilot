# Quality Review: F4 QA Test Completion

## Review Scope

Reviewed test files from commits `443d84b` and `7efee40`:
- `tests/unit/services/test_lecture_bm25_store.py` (368 lines, NEW)
- `tests/unit/services/test_lecture_followup_service.py` (644 lines, NEW)
- `tests/unit/services/test_lecture_verifier_service.py` (826 lines, EXPANDED)
- `tests/api/v4/test_lecture_qa.py` (1367 lines, EXPANDED)

## Review Date

2026-02-21

## Validation Status

| Check | Status |
|-------|--------|
| Tests pass | Not verified (requires execution) |
| Ruff lint | Not verified |
| Type check | Not verified |

---

## Findings

### [High] Magic Numbers in Time-Based Assertions

**File**: `test_lecture_bm25_store.py`
**Lines**: 211-218

**Current Code**:
```python
async def modify_with_lock(session_id: str, delay: float) -> None:
    lock = await store.acquire_lock(session_id)
    async with lock:
        execution_order.append(f"start-{session_id}")
        await asyncio.sleep(delay)  # 0.01
        execution_order.append(f"end-{session_id}")

await asyncio.gather(
    modify_with_lock("session-1", 0.01),
    modify_with_lock("session-1", 0.01),
)
```

**Issue**: Hardcoded `0.01` sleep duration and repeated calls with same value.

**Recommendation**:
```python
LOCK_TEST_DELAY_MS = 10  # Constant for serialization tests

async def modify_with_lock(session_id: str, delay_ms: int = LOCK_TEST_DELAY_MS) -> None:
    lock = await store.acquire_lock(session_id)
    async with lock:
        execution_order.append(f"start-{session_id}")
        await asyncio.sleep(delay_ms / 1000)
        execution_order.append(f"end-{session_id}")
```

---

### [High] Inconsistent Async Test Decorator Usage

**File**: `test_lecture_verifier_service.py`
**Lines**: 34-65, 273-295

**Current Code**:
```python
def test_parse_verification_result_handles_string_false_as_false() -> None:
    """String 'false' must not be treated as truthy pass."""
    service = AzureOpenAILectureVerifierService(...)
    result = service._parse_verification_result(...)  # Sync method

async def test_verify_with_no_sources() -> None:
    """Empty sources should return deterministic failure result."""
    service = AzureOpenAILectureVerifierService(...)
    result = await service.verify(...)  # Async method
```

**Issue**: Mix of `@pytest.mark.asyncio` decorated and non-decorated tests in same file. Lines 34-65 lack `@pytest.mark.asyncio` but test sync methods - this is correct but inconsistent pattern with async tests.

**Recommendation**: Group sync tests separately from async tests with clear section markers, or add a module-level `pytest_plugins` for auto-async marking if appropriate.

---

### [Medium] Test Naming Inconsistency - Japanese vs English

**File**: `test_lecture_followup_service.py`
**Lines**: 40-42, 166-168

**Current Code**:
```python
def test_format_history_with_turns(sample_qa_turns):
    """Format history with QA turns."""
    result = service._format_history(sample_qa_turns)
    assert "会話履歴:" in result
    assert "Q1: BM25アルゴリズムとは何ですか？" in result
```

**Issue**: Test data uses Japanese (`BM25アルゴリズムとは何ですか？`) mixed with English code. This makes tests less maintainable for international contributors and harder to debug.

**Recommendation**: Use English test data or provide a clear fixture with transliteration:
```python
@pytest.fixture
def sample_qa_turns():
    """Sample QA turns for testing."""
    return [
        QATurn(
            id="turn-1",
            session_id="test-session",
            feature="lecture_qa",
            question="What is BM25 algorithm?",  # English for test stability
            answer="BM25 is a ranking function for information retrieval.",
            # ...
        ),
    ]
```

---

### [Medium] Helper Function Outside Test Class Structure

**File**: `test_lecture_verifier_service.py`
**Lines**: 16-27

**Current Code**:
```python
def _make_source(text: str, timestamp: str = "10:00") -> LectureSource:
    """Create a valid LectureSource for testing."""
    return LectureSource(
        chunk_id="test-chunk",
        type="speech",
        text=text,
        timestamp=timestamp,
        bm25_score=0.9,
    )
```

**Issue**: Module-level helper function `_make_source` is used throughout but not organized within a fixture class. This is acceptable but could be better structured.

**Recommendation**: Move to a fixture for better pytest integration:
```python
@pytest.fixture
def make_source():
    """Factory fixture for creating LectureSource instances."""
    def _make(text: str, timestamp: str = "10:00") -> LectureSource:
        return LectureSource(
            chunk_id="test-chunk",
            type="speech",
            text=text,
            timestamp=timestamp,
            bm25_score=0.9,
        )
    return _make
```

---

### [Medium] Weak Assertions in Followup Tests

**File**: `test_lecture_followup_service.py`
**Lines**: 136-139, 175-176

**Current Code**:
```python
assert (
    "BM25アルゴリズム" in result.standalone_query
    or "それ" in result.standalone_query
)
```

**Issue**: `or` assertion makes test pass even if query wasn't properly rewritten. If "それ" remains in output, the rewrite failed but test still passes.

**Recommendation**:
```python
assert "BM25アルゴリズム" in result.standalone_query
assert "それ" not in result.standalone_query  # Verify pronoun was resolved
```

---

### [Medium] Incomplete Error Coverage in Verifier Tests

**File**: `test_lecture_verifier_service.py`
**Lines**: 152-178

**Current Code**:
```python
async def test_verify_with_http_error_429():
    """HTTPError with 429 status should raise LectureVerifierError."""
    # Tests 429 and 500, but missing other relevant codes
```

**Issue**: Only tests 429 and 500 HTTP errors. Missing 401 (auth), 403 (quota), 400 (bad request).

**Recommendation**: Add tests for remaining error codes from Azure OpenAI documentation (400, 401, 403, 503).

---

### [Low] Redundant Comment - Code is Self-Documenting

**File**: `test_lecture_bm25_store.py`
**Lines**: 14-15, 28-32

**Current Code**:
```python
async def test_put_and_get_index(self) -> None:
    """Store and retrieve BM25 index."""
    # ... docstring already says "Store and retrieve"

async def test_get_nonexistent_returns_none(self) -> None:
    """Getting non-existent session should return None."""
    # ... docstring is self-explanatory
```

**Issue**: Comments repeat what the docstring already states.

**Recommendation**: Remove redundant comments or add domain-specific rationale.

---

### [Low] AAA Pattern Not Strictly Followed in Some Tests

**File**: `test_lecture_bm25_store.py`
**Lines**: 104-122

**Current Code**:
```python
async def test_concurrent_get_operations(self) -> None:
    """Multiple concurrent reads should work correctly."""
    store = LectureBM25Store()
    chunks = [{"id": "chunk-1", "text": "Shared data"}]
    await store.put("session-1", chunks, [["shared", "data"]], "v1")

    # Concurrent reads
    results = await asyncio.gather(
        store.get("session-1"),
        store.get("session-1"),
        # ...
    )

    # All should succeed
    assert all(r is not None for r in results)
```

**Issue**: Comment "Concurrent reads" appears mid-test. AAA pattern would separate this more clearly.

**Recommendation**:
```python
async def test_concurrent_get_operations(self) -> None:
    """Multiple concurrent reads should work correctly."""
    # Arrange
    store = LectureBM25Store()
    chunks = [{"id": "chunk-1", "text": "Shared data"}]
    await store.put("session-1", chunks, [["shared", "data"]], "v1")

    # Act
    results = await asyncio.gather(
        store.get("session-1"),
        store.get("session-1"),
        store.get("session-1"),
        store.get("session-1"),
        store.get("session-1"),
    )

    # Assert
    assert all(r is not None for r in results)
    assert all(r.session_id == "session-1" for r in results)
```

---

### [Low] Missing Type Hints on Test Helper Function

**File**: `test_lecture_verifier_service.py`
**Lines**: 16-27

**Current Code**:
```python
def _make_source(text: str, timestamp: str = "10:00") -> LectureSource:
```

**Issue**: Return type is present, which is good. No issue here - actually follows best practices.

**Status**: False positive removed - code is correct.

---

### [Medium] Test Independence Concern - Shared State

**File**: `test_lecture_followup_service.py`
**Lines**: 67-84, 142-156

**Issue**: Multiple tests create `SqlAlchemyLectureFollowupService` with empty `openai_api_key=""`. While each test creates a new instance, the mock setup is repetitive and could be consolidated.

**Recommendation**: Use a fixture with params for different configurations:
```python
@pytest.fixture
def followup_service_no_azure(mock_db_session):
    """Service with Azure OpenAI disabled."""
    return SqlAlchemyLectureFollowupService(
        db=mock_db_session,
        openai_api_key="",
    )

@pytest.fixture
def followup_service_with_azure(mock_db_session):
    """Service with Azure OpenAI enabled."""
    return SqlAlchemyLectureFollowupService(
        db=mock_db_session,
        openai_api_key="test-key",
        openai_endpoint="https://test.openai.azure.com/",
    )
```

---

### [Low] Duplicate Test Setup Code

**File**: `test_lecture_qa.py`
**Lines**: 85-115, 139-166, 247-274

**Current Code**:
```python
async def test_post_qa_index_build_returns_success(...):
    async with session_factory() as session:
        from datetime import UTC, datetime
        from app.models.lecture_session import LectureSession
        from app.models.speech_event import SpeechEvent

        session_id = "test_session_qa_001"
        session_obj = LectureSession(...)
        # ...
```

**Issue**: Session setup code is duplicated across tests with only session_id changing.

**Recommendation**: Create a fixture that handles session creation:
```python
@pytest.fixture
async def lecture_session_with_events(session_factory):
    """Create a lecture session with speech events."""
    async def _create(session_id: str, event_count: int = 3):
        async with session_factory() as session:
            # ... common setup
        return session_id
    return _create
```

---

### [Low] Inconsistent Docstring Styles

**File**: All test files

**Current**: Mix of:
- """Store and retrieve BM25 index."""
- """Getting non-existent session should return None."""
- """Verify the query was executed"""

**Issue**: No consistent pattern for docstring voice (imperative vs descriptive).

**Recommendation**: Follow pytest convention - use imperative mood describing what is being tested:
- "test_name" -> """Should do X when Y"""

---

### [High] Missing Test for Race Condition in BM25 Store

**File**: `test_lecture_bm25_store.py`

**Issue**: Tests cover concurrent gets and concurrent puts to different sessions, but don't test concurrent puts to the SAME session with lock contention.

**Recommendation**: Add test:
```python
async def test_concurrent_put_same_session_serializes():
    """Concurrent puts to same session should be serialized."""
    store = LectureBM25Store()
    execution_order = []

    async def put_with_version(version: int):
        await store.put("session-1", [{"id": f"c{version}"}], [["x"]], f"v{version}")
        execution_order.append(version)

    await asyncio.gather(
        put_with_version(1),
        put_with_version(2),
        put_with_version(3),
    )

    # All puts should complete (serialized)
    assert len(execution_order) == 3
```

---

### [Medium] Verifier Test - Missing Edge Case for Empty Answer String

**File**: `test_lecture_verifier_service.py`
**Lines**: 276-291

**Current Code**:
```python
async def test_local_verify_with_empty_answer():
    """Local fallback should fail with empty answer."""
    result = await service.verify(
        question="テスト質問",
        answer="   ",  # Only whitespace
        sources=[_make_source("講義資料")],
    )
    assert result.passed is False
```

**Issue**: Good test, but missing case for truly empty string `""` and `None` (if allowed by schema).

**Recommendation**: Add parametrized test:
```python
@pytest.mark.parametrize("answer", ["", "   ", "\n\t"])
async def test_local_verify_with_empty_variations(answer):
    """Local fallback should fail with various empty inputs."""
    # ...
```

---

## Positive Findings

### Excellent Test Organization

**File**: `test_lecture_bm25_store.py`

The test class organization is exemplary:
- `TestLectureBM25StoreBasicOperations` - CRUD operations
- `TestLectureBM25StoreConcurrentOperations` - Concurrency
- `TestLectureBM25StoreLockManagement` - Lock behavior
- `TestLectureBM25StoreChunkMap` - Data structure specifics
- `TestLectureBM25IndexDataclass` - Data model validation
- `TestLectureBM25StoreEdgeCases` - Boundary conditions

This follows single responsibility principle at the test class level.

### Comprehensive Error Handling Tests

**File**: `test_lecture_verifier_service.py`

Tests cover:
- HTTP errors (429, 500)
- Network errors (URLError)
- JSON parse errors
- Malformed responses
- Empty responses
- Source content extraction edge cases

This demonstrates thorough error path testing.

### Well-Structured E2E Tests

**File**: `test_lecture_qa.py`

The `test_e2e_lecture_qa_full_workflow` test (lines 923-1130) is excellent:
- Clear step-by-step documentation
- Database verification at each step
- Full API flow coverage
- Proper cleanup assertion

### Good Mock Usage

**File**: `test_lecture_followup_service.py`

Uses `unittest.mock.patch` appropriately for external dependencies (urlopen) and correctly mocks AsyncSession behavior.

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total test functions reviewed | ~70 |
| High severity findings | 3 |
| Medium severity findings | 7 |
| Low severity findings | 5 |
| Positive patterns | 4 |

---

## Recommendations Priority

1. **Address magic numbers** - Define constants for test timing values
2. **Strengthen assertions** - Remove `or` conditions that mask failures
3. **Add missing edge case tests** - Empty strings, race conditions, HTTP codes
4. **Reduce duplication** - Extract common setup into fixtures
5. **Standardize docstrings** - Use consistent imperative mood

---

## Conclusion

The test suite demonstrates strong coverage and good organization. Main areas for improvement are:
1. Eliminating magic numbers
2. Strengthening weak assertions
3. Adding edge case coverage for race conditions and error handling
4. Reducing test setup duplication

Overall quality is **GOOD** with specific improvements needed for production robustness.
