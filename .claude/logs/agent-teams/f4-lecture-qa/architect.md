# Architect Work Log

## Project: F4 Lecture QA
## Role: Architect
## Date: 2026-02-21

## Tasks Completed

### 1. Existing Codebase Analysis ✓
- Analyzed procedure_qa_service.py for QA orchestration pattern
- Reviewed existing models: LectureSession, SpeechEvent, QATurn
- Identified service layer patterns: RetrievalService, AnswererService, QAService
- Found auth patterns: X-Lecture-Token + X-User-Id headers
- Reviewed API routing patterns in procedure.py and lecture.py

### 2. Codex Architecture Consultation ✓
- Consulted Codex CLI for architecture design
- Received comprehensive module structure recommendation
- Got data flow diagrams for index build and ask QA
- Obtained key interface definitions (Protocol-based)
- Received error handling strategy with domain exceptions
- Got implementation task breakdown with dependencies

### 3. Architecture Documentation ✓
- Updated .claude/docs/DESIGN.md with F4 Lecture QA section
- Documented module structure with 9 service components
- Added data flow diagrams (index build, ask QA)
- Documented key interfaces (5 Protocols)
- Added error handling table (5 domain exceptions)
- Documented design decisions with rationale
- Added implementation task breakdown (12 tasks)

### 4. Researcher Coordination ✓
- Requested rank-bm25 library research from Researcher
- Specified research topics: API usage, context expansion, Japanese tokenization
- Received comprehensive research findings:
  - rank-bm25 limitations (no incremental updates, no multi-field support)
  - Azure OpenAI On Your Data API patterns
  - LLM-based verifier design (claim-by-claim verification)
  - Lecture QA best practices (chunking, context window, follow-up)
  - Integration with existing patterns

## Architecture Decisions Made

### Module Structure (9 Components)
1. **API Layer**: `app/api/v4/lecture_qa.py`
2. **Schemas**: `app/schemas/lecture_qa.py`
3. **QA Orchestrator**: `app/services/lecture_qa_service.py`
4. **Index Builder**: `app/services/lecture_index_service.py`
5. **BM25 Cache**: `app/services/lecture_bm25_store.py`
6. **Retrieval**: `app/services/lecture_retrieval_service.py`
7. **Follow-up**: `app/services/lecture_followup_service.py`
8. **Answerer**: `app/services/lecture_answerer_service.py`
9. **Verifier**: `app/services/lecture_verifier_service.py`

### Key Design Patterns

| Pattern | Description |
|---------|-------------|
| **Protocol-based interfaces** | All services defined as Protocols for testability |
| **Orchestration pattern** | retrieve → answer → verify → persist |
| **In-memory BM25 cache** | Session-scoped index storage with asyncio.Lock |
| **Follow-up rewrite** | Convert follow-up to standalone query using history |
| **Source expansion** | source-plus-context includes neighboring chunks |
| **Verifier repair** | Single repair attempt with fallback |

### Data Flow Design

**Index Build**:
```
SpeechEvents → Tokenize → BM25Okapi → BM25Store → qa_index_built=true
```

**Ask QA**:
```
Question → FollowupService (rewrite) → RetrievalService (BM25)
  → AnswererService (Azure) → VerifierService (citation check)
  → QATurn persist
```

### Error Handling Strategy

| Exception | HTTP | Use Case |
|-----------|------|----------|
| LectureSessionNotFoundError | 404 | Session not found |
| LectureSessionInactiveError | 409 | Session not active |
| LectureQAIndexNotBuiltError | 409 | Index not built |
| LectureQAIndexBuildInProgressError | 409 | Build in progress |
| AzureOpenAITimeoutError | 503 | Azure timeout |

## Researcher Integration

### Research Findings Incorporated
1. **BM25 Limitations**: Full rebuild required (no incremental updates)
2. **Multi-field Challenge**: Use separate indexes + score fusion
3. **Japanese Tokenization**: SudachiPy integration required
4. **Verifier Latency**: Additional LLM call (accepted as design trade-off)
5. **Chunking Strategy**: 256-512 tokens, 10-20% overlap

### Adjustments Based on Research
- Added score fusion pattern for future multi-field support
- Specified SudachiPy as Japanese tokenizer dependency
- Designed VerifierService as separate component for modularity
- Included context_window parameter for neighbor expansion

## Dependencies Identified

```toml
[project]
dependencies = [
    "rank-bm25>=0.2",      # BM25 local search
    "openai>=1.0",         # Azure OpenAI client
    "sudachipy>=0.6",      # Japanese tokenizer
]
```

## Implementation Plan

| Phase | Tasks |
|-------|-------|
| **Phase 1**: Foundation | 1-3: dependencies, schemas, BM25 store |
| **Phase 2**: Index | 4: index service |
| **Phase 3**: Retrieval** | 6: retrieval service |
| **Phase 4**: AI Services** | 5,7,8: follow-up, answerer, verifier |
| **Phase 5**: Orchestration** | 9: QA service |
| **Phase 6**: API** | 10: routes + DI |
| **Phase 7**: Testing** | 11-12: unit + integration |

## Files Modified/Created

### Modified
- `.claude/docs/DESIGN.md` - Added Sprint4 F4 Lecture QA section

### To Be Created (Implementation Phase)
- `app/api/v4/lecture_qa.py`
- `app/schemas/lecture_qa.py`
- `app/services/lecture_qa_service.py`
- `app/services/lecture_index_service.py`
- `app/services/lecture_bm25_store.py`
- `app/services/lecture_retrieval_service.py`
- `app/services/lecture_followup_service.py`
- `app/services/lecture_answerer_service.py`
- `app/services/lecture_verifier_service.py`
- `tests/api/v4/test_lecture_qa.py`
- `tests/unit/services/test_lecture_qa_service.py`

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| BM25 rebuild time | Medium | Async build with progress tracking |
| Verifier latency | Medium | Single repair + timeout |
| Japanese tokenization cost | Low | SudachiPy (lightweight) |
| Azure rate limits | Medium | Retry with exponential backoff |

## Handoff Notes

### For Implementers
1. Follow existing patterns from `procedure_qa_service.py`
2. Use Protocol interfaces for all services
3. Reuse `QATurn` with `feature="lecture_qa"`
4. Implement BM25Store with asyncio.Lock for thread safety
5. Use Azure OpenAI with timeout and retry logic

### For Security Reviewer
1. Verify session ownership in all operations
2. Check user_id context propagation
3. Validate BM25 index access boundaries
4. Review Azure OpenAI key handling

## Status

**Architecture Phase: COMPLETE ✓**

All architectural decisions documented. Ready for implementation phase.
