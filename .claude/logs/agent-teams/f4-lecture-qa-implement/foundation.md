# Foundation Implementer Work Log

**Agent**: foundation
**Date**: 2026-02-21
**Project**: F4 Lecture QA

---

## Tasks Completed

### Task #3: Add rank-bm25 dependency

**Status**: Completed

**Changes**:
- Added `rank-bm25>=0.2.2` to `pyproject.toml` dependencies
- Ran `uv sync` to update dependencies

**Files Modified**:
- `/home/argo/sit-copilot/pyproject.toml`

**Verification**:
- `uv sync` completed successfully
- `rank-bm25==0.2.2` installed

---

### Task #4: Create lecture_qa schemas

**Status**: Completed

**Files Created**:
- `/home/argo/sit-copilot/app/schemas/lecture_qa.py`

**Schemas Implemented**:

1. **LectureSource** - BM25 retrieval result with citation info
   - `chunk_id`: str
   - `type`: Literal["speech", "visual"]
   - `text`: str
   - `timestamp`: str | None ("MM:SS" format)
   - `start_ms`: int | None
   - `end_ms`: int | None
   - `speaker`: str | None
   - `bm25_score`: float
   - `is_direct_hit`: bool (True for direct match, False for context expansion)

2. **LectureCitation** - Citation format for API responses
   - `chunk_id`: str
   - `type`: Literal["speech", "visual"]
   - `timestamp`: str | None
   - `text`: str (snippet)

3. **LectureAskRequest** - Request schema for `/qa/ask`
   - `session_id`: str
   - `question`: str (validated not blank)
   - `lang_mode`: Literal["ja", "easy-ja", "en"] (default: "ja")
   - `retrieval_mode`: Literal["source-only", "source-plus-context"] (default: "source-only")
   - `top_k`: int (1-20, default: 5)
   - `context_window`: int (0-5, default: 1)

4. **LectureAskResponse** - Response schema for `/qa/ask`
   - `answer`: str
   - `confidence`: Literal["high", "medium", "low"]
   - `sources`: list[LectureSource]
   - `verification_summary`: str | None
   - `action_next`: str
   - `fallback`: str | None

5. **LectureFollowupRequest** - Request schema for `/qa/followup`
   - `session_id`: str
   - `question`: str
   - `lang_mode`: Literal["ja", "easy-ja", "en"]
   - `retrieval_mode`: Literal["source-only", "source-plus-context"]
   - `top_k`: int
   - `context_window`: int
   - `history_turns`: int (1-10, default: 3)

6. **LectureFollowupResponse** - Response schema for `/qa/followup`
   - `answer`: str
   - `confidence`: Literal["high", "medium", "low"]
   - `sources`: list[LectureSource]
   - `verification_summary`: str | None
   - `action_next`: str
   - `fallback`: str | None
   - `resolved_query`: str (standalone query after context resolution)

7. **LectureIndexBuildRequest** - Request schema for `/qa/index/build`
   - `session_id`: str
   - `rebuild`: bool (default: False)

8. **LectureIndexBuildResponse** - Response schema for `/qa/index/build`
   - `index_version`: str
   - `chunk_count`: int
   - `built_at`: datetime
   - `status`: Literal["success", "skipped"]

**Files Modified**:
- `/home/argo/sit-copilot/app/schemas/__init__.py` - Added lecture_qa exports

**Verification**:
- Python syntax check passed
- Follows existing patterns from `procedure.py` and `lecture.py`
- Uses `ConfigDict(extra="forbid", from_attributes=True)` for Pydantic v2
- Field validators for session_id and question normalization

---

## Summary

All assigned tasks completed successfully:
- Task #3: Added rank-bm25 dependency
- Task #4: Created lecture_qa schemas with 8 Pydantic models

The schemas follow established codebase patterns and are ready for service layer implementation.
