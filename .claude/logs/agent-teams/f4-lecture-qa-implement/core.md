# Core Services Implementation Work Log

**Agent**: core
**Date**: 2026-02-21
**Project**: F4 Lecture QA Implementation

## Assigned Tasks

### Task #3: Create lecture_retrieval_service.py ✅ COMPLETED
**Status**: Completed
**File**: `app/services/lecture_retrieval_service.py`

**Implemented Components**:
1. **BM25TokenCache** - Immutable cache for tokenized corpus
   - Stores tokenized corpus, chunk IDs, and chunk metadata
   - Prevents re-tokenization on each search

2. **LectureRetrievalIndex** - BM25 index wrapper
   - Holds BM25Okapi instance with metadata
   - Provides get_scores() method

3. **LectureRetrievalService** (Protocol) - Interface for retrieval
   - retrieve(): Search with mode and context expansion
   - get_index()/set_index()/has_index()/remove_index(): Index management

4. **BM25LectureRetrievalService** - Implementation
   - In-memory index storage keyed by session_id
   - Source-only mode: Returns direct BM25 hits
   - Source-plus-context mode: Expands with neighboring chunks
   - Uses asyncio.to_thread() for CPU-bound BM25 operations
   - Deduplicates expanded results by chunk_id
   - Marks is_direct_hit flag for proper citation

**Key Features**:
- Simple whitespace tokenization (lowercase split)
- BM25 parameters: k1=1.2, b=0.5 (tuned for Japanese lecture content)
- Context window: configurable neighbor chunks
- Thread-safe: Creates BM25 instance per search request

---

### Task #4: Create lecture_index_service.py ✅ COMPLETED
**Status**: Completed
**File**: `app/services/lecture_index_service.py`

**Implemented Components**:
1. **LectureIndexService** (Protocol) - Interface for index building
   - build_index(): Build or rebuild BM25 index

2. **BM25LectureIndexService** - Implementation
   - Validates session ownership (session_id + user_id)
   - Fetches SpeechEvent with is_final=True only
   - Orders by start_ms for temporal consistency
   - Builds BM25Okapi index via asyncio.to_thread()
   - Stores index in RetrievalService
   - Sets LectureSession.qa_index_built=True
   - Per-session asyncio.Lock for concurrency control

**Key Features**:
- Ownership validation: Prevents cross-user index access
- Skip if already built (rebuild=False)
- Handles empty sessions (0 events)
- Timestamp formatting: MM:SS from milliseconds
- UUID version generation for index tracking

---

## File Changes

### New Files
- `app/services/lecture_retrieval_service.py` (210 lines)
- `app/services/lecture_index_service.py` (290 lines)

### Modified Files
- `app/services/__init__.py` - Added exports for new services

---

## Verification Results

### Linting
```bash
uv run ruff check app/services/lecture_retrieval_service.py
uv run ruff check app/services/lecture_index_service.py
uv run ruff check app/services/__init__.py
```
**Result**: All checks passed ✅

### Type Checking
```bash
uv run ty check app/services/lecture_retrieval_service.py app/services/lecture_index_service.py
```
**Result**: All checks passed ✅

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| In-memory index cache | Low latency for active sessions; simple lifecycle |
| SpeechEvent.id as chunk_id | Preserves timestamp precision for citations |
| is_final=True filter | Index only finalized subtitle content |
| Per-session Lock | Prevents concurrent build races |
| asyncio.to_thread() | Offloads CPU-bound BM25 operations |
| Simple whitespace tokenization | Fast for MVP; SudachiPy later for Japanese |
| k1=1.2, b=0.5 | Lower values for shorter Japanese lecture chunks |
| Protocol interfaces | Testability and mock-friendly design |

---

## Integration Points

### Dependencies
- `rank-bm25>=0.2.2` (already added by Foundation)
- `SpeechEvent` model (lecture_session.py, speech_event.py)
- `LectureSession.qa_index_built` flag
- `LectureSource` schema (lecture_qa.py)

### Used By
- `lecture_qa_service.py` (orchestrator) - will use these services
- API routes (`/api/v4/lecture/qa/index/build`, `/api/v4/lecture/qa/ask`)

---

## Notes for Reviewers

1. **Tokenization**: Currently uses simple whitespace + lowercase. For production Japanese, should integrate SudachiPy.

2. **BM25 Parameters**: k1=1.2 and b=0.5 are starting points for Japanese lecture content. May need tuning based on real data.

3. **Thread Safety**: rank-bm25 is NOT thread-safe. We create new BM25Okapi instances per search request via asyncio.to_thread().

4. **Memory**: Indexes are kept in-process memory. For multi-instance deployment, consider Redis or shared cache.

5. **Empty Sessions**: Index is marked as built even with 0 events. This allows ask endpoint to return "no content" vs "index not built".

---

## Next Steps

For QA Orchestrator:
1. Wire LectureIndexService and LectureRetrievalService in LectureQAService
2. Implement LectureAnswererService (Azure OpenAI)
3. Implement LectureVerifierService (LLM-based verification)
4. Implement LectureFollowupService (conversation history)

For API Layer:
1. Create `app/api/v4/lecture_qa.py` with DI wiring
2. Register router in main.py
3. Add auth dependencies (X-Lecture-Token, X-User-Id)

---

**Agent**: core
**Status**: Tasks completed, waiting for teammates to finish
**Work Time**: ~30 minutes
