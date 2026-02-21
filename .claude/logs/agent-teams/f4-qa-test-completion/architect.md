# Work Log: Architect

## Summary
Designed comprehensive test architecture for F4 Lecture QA services to raise coverage from 81% to 85%+. Codex provided detailed test patterns, mock strategies, and implementation plan for three target services.

## Tasks Completed
- [x] **Analyze existing codebase**: Read source files for `lecture_bm25_store.py`, `lecture_verifier_service.py`, `lecture_followup_service.py`
- [x] **Study existing test patterns**: Reviewed `test_lecture_verifier_service.py`, `test_lecture_retrieval_service.py`, `conftest.py`
- [x] **Consult Codex for test architecture**: Retrieved comprehensive test design from Codex CLI
- [x] **Create implementation plan**: 8-step dependency-ordered implementation plan
- [x] **Document test case checklists**: Detailed test scenarios for each service
- [x] **Design mock strategy**: Azure OpenAI HTTP mock patterns following existing codebase conventions
- [x] **Update DESIGN.md**: Added F4 QA test completion architecture entry
- [x] **Create work log**: This file

## Design Decisions

### Test Architecture

1. **Service-first unit testing**
   - Prioritize deterministic unit tests at service boundaries
   - Reuse existing API/integration tests only for critical wiring checks
   - No test-class inheritance; use fixture composition

2. **Standardized Azure OpenAI HTTP mocking**
   - Follow existing `urlopen` patch pattern from `test_lecture_summary_generator_service.py`
   - Use `@patch("app.services.<module>.urlopen")`
   - Mock responses cover: success, HTTPError, URLError, JSON parse failure, missing content

3. **BM25 store testing**
   - No external I/O mocking needed (pure in-memory operations)
   - Use `asyncio.create_task()` for concurrent access testing
   - Test lock lifecycle: acquisition, reuse, cross-session isolation

4. **Database-dependent tests (followup)**
   - Reuse existing `db_session` fixture from `conftest.py`
   - Seed helper fixtures for `LectureSession` and `QATurn` creation
   - Test ownership filtering and ordering guarantees

### Implementation Plan (Dependency Order)

| Step | Task | Dependencies |
|------|------|--------------|
| 1 | Create base fixtures (`sample_sources`, HTTP mock helpers) | None |
| 2 | Implement `test_lecture_bm25_store.py` | 1 |
| 3 | Expand `test_lecture_verifier_service.py` (local/parser branches) | 1 |
| 4 | Add Azure communication tests to verifier | 3 |
| 5 | Implement DB history tests for followup | 1 |
| 6 | Add rewrite tests for followup | 5 |
| 7 | Add integration regression tests | 4, 6 |
| 8 | Run coverage gate and close gaps | All |

### Coverage Targets

- **`lecture_bm25_store.py`**: 0% → 95%+
  - Methods: `get`, `put`, `delete`, `acquire_lock`, `has_index`
  - Branches: lock existing/new, index existing/missing

- **`lecture_verifier_service.py`**: 49% → 85%+
  - Methods: `verify`, `_call_openai_verification`, `_parse_verification_result`, `repair_answer`, `_call_openai_repair`, local/normalize/extract helpers
  - Branches: fail-closed (no-source, parse fail, network fail, unsupported claims)

- **`lecture_followup_service.py`**: 35% → 85%+
  - Methods: `resolve_query`, `_load_history`, `_format_history`, `_rewrite_to_standalone`, `_simple_rewrite`, `_call_openai_rewrite`, readiness/url/content helpers
  - Branches: no-history, local rewrite, Azure success/failure, ownership filter

### Mock Strategy Details

```python
# Azure OpenAI HTTP mock pattern
@patch("app.services.lecture_verifier_service.urlopen")
def test_verification_success(mock_urlopen):
    # Success response
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"choices":[{"message":{"content":"{\\"passed\\":true,\\"summary\\":\\"OK\\",\\"unsupported_claims\\":[]}"}}]}'
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)
    mock_urlopen.return_value = mock_response
    # ... test code

# HTTPError/URLError handling
@patch("app.services.lecture_verifier_service.urlopen")
def test_verification_http_error(mock_urlopen):
    mock_urlopen.side_effect = HTTPError("url", 500, "Error", {}, None)
    # ... verify LectureVerifierError raised
```

### Test Case Checklists

#### lecture_bm25_store.py
- [ ] Happy path: `put` then `get` succeeds
- [ ] `has_index=True` after put
- [ ] `delete` removes index
- [ ] `delete` on non-existent key (no exception)
- [ ] `get` on non-existent key returns `None`
- [ ] `acquire_lock` returns same lock for same session
- [ ] `acquire_lock` returns different lock for different sessions
- [ ] Concurrent `put/get` with lock safety

#### lecture_verifier_service.py
- [ ] Azure success returns `passed=True`
- [ ] Empty sources triggers fail-closed
- [ ] HTTPError raises `LectureVerifierError`
- [ ] URLError raises `LectureVerifierError`
- [ ] Invalid JSON raises `LectureVerifierError`
- [ ] String `"false"` parsed as `False` (not truthy)
- [ ] Invalid `passed` type triggers fail-closed
- [ ] `unsupported_claims` normalized (non-string items filtered)
- [ ] `passed=True` with `unsupported_claims` coerced to `False`
- [ ] Local verify returns match when fragment exists
- [ ] Local verify returns fail when no fragment match
- [ ] Repair answer returns corrected text
- [ ] Repair returns `None` on unrecoverable
- [ ] Local repair returns snippet from first source

#### lecture_followup_service.py
- [ ] History exists returns formatted string
- [ ] Empty history returns empty string
- [ ] No history returns original question unchanged
- [ ] Local rewrite with "それは" prefix prepends context
- [ ] Azure rewrite success returns standalone query
- [ ] Azure rewrite failure falls back to simple rewrite
- [ ] Other user's session returns empty history (ownership)
- [ ] `history_turns` limit is respected
- [ ] Simple rewrite handles Q1 extraction from history
- [ ] `_is_azure_openai_ready` validates key/endpoint/model

## Codex Consultations

### Question 1: Test Architecture Design
**Prompt**: Design comprehensive test architecture for F4 Lecture QA services (bm25_store, verifier, followup) including fixtures, mocks, test cases, and implementation plan.

**Key Insights**:
- Follow existing `FakeAzureSearchService` and `urlopen` patch patterns
- Use fixture composition over class inheritance
- BM25 store has no external dependencies (pure in-memory)
- Verifier needs HTTP mock coverage for all error branches
- Followup needs DB seeding fixtures for conversation history
- Implement in dependency order: fixtures → bm25 → verifier → followup

## Communication with Teammates
- → **Implementer A/B/C**: Test architecture designed. See `.claude/logs/agent-teams/f4-qa-test-completion/architect.md` for detailed plan. Base fixtures (sample_sources, HTTP mock helpers) should be implemented first in `tests/conftest.py` or shared test utilities.
- → **Reviewer**: Coverage targets are 95%+ for bm25_store (currently 0%), 85%+ for verifier (49%), 85%+ for followup (35%). Key areas: fail-closed branches, local fallbacks, Azure error handling, lock safety, ownership filtering.

## Issues Encountered
- None

## Recommendations
1. Implementer A: Start with `test_lecture_bm25_store.py` (foundation tests, no external deps)
2. Implementer B: Expand `test_lecture_verifier_service.py` (has existing tests to build upon)
3. Implementer C: Implement `test_lecture_followup_service.py` (needs DB fixtures)
4. After implementation: Run `uv run pytest --cov=app/services/lecture_bm25_store --cov=app/services/lecture_verifier_service --cov=app/services/lecture_followup_service --cov-report=term-missing` to verify 85%+ threshold
