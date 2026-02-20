# Project Design Document

> This document tracks design decisions made during conversations.
> Updated automatically by the `design-tracker` skill.

## Overview

Claude Code Orchestra is a multi-agent collaboration framework. Claude Code (200K context) is the orchestrator, with Codex CLI for planning/design/complex code, Gemini CLI (1M context) for codebase analysis, research, and multimodal reading, and subagents (Opus) for code implementation and Codex delegation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code Lead (Opus 4.6 — 200K context)                      │
│  Role: Orchestration, user interaction, task management           │
│                                                                   │
│  ┌──────────────────────┐  ┌──────────────────────┐             │
│  │ Agent Teams (Opus)    │  │ Subagents (Opus)      │             │
│  │ (parallel + comms)    │  │ (isolated + results)  │             │
│  │                       │  │                       │             │
│  │ Researcher ←→ Archit. │  │ Code implementation   │             │
│  │ Implementer A/B/C     │  │ Codex consultation    │             │
│  │ Security/Quality Rev. │  │ Gemini consultation   │             │
│  └──────────────────────┘  └──────────────────────┘             │
│                                                                   │
│  External CLIs:                                                   │
│  ├── Codex CLI (gpt-5.3-codex) — planning, design, complex code  │
│  └── Gemini CLI (1M context) — codebase analysis, research,      │
│       multimodal reading                                          │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Roles

| Agent | Role | Responsibilities |
|-------|------|------------------|
| Claude Code（メイン） | 全体統括 | ユーザー対話、タスク管理、簡潔なコード編集 |
| general-purpose（Opus） | 実装・Codex委譲 | コード実装、Codex委譲、ファイル操作 |
| gemini-explore（Opus） | 大規模分析・調査 | コードベース理解、外部リサーチ、マルチモーダル読取 |
| Codex CLI | 計画・難実装 | アーキテクチャ設計、実装計画、複雑なコード、デバッグ |
| Gemini CLI（1M context） | 分析・調査・読取 | コードベース分析、外部リサーチ、マルチモーダル読取 |

---

## Sprint0 Backend Architecture (2026-02-21)

### Project: FastAPI Backend Foundation

**Goal**: Create FastAPI backend foundation with green pytest and /health endpoint returning 200.

### Directory Structure

```
sit-copilot/
├── app/                          # Main application module
│   ├── __init__.py
│   ├── main.py                   # FastAPI instance & root router
│   │
│   ├── api/                      # API routes (versioned)
│   │   ├── __init__.py
│   │   └── v4/                   # API v4
│   │       ├── __init__.py
│   │       └── health.py         # Health endpoint
│   │
│   ├── core/                     # Core infrastructure
│   │   ├── __init__.py
│   │   └── config.py             # Settings, environment variables
│   │
│   └── schemas/                  # Pydantic models
│       ├── __init__.py
│       └── health.py             # Health response schema
│
├── tests/                        # pytest tests
│   ├── __init__.py
│   ├── conftest.py               # Shared fixtures
│   ├── api/
│   │   ├── __init__.py
│   │   └── test_health.py        # Health endpoint tests
│   └── unit/
│       └── (future unit tests)
│
├── pyproject.toml                # Project config & dependencies
└── README.md
```

### Layered Architecture

```
┌─────────────────────────────────┐
│   API Layer (routes)            │  ← HTTP endpoints only
├─────────────────────────────────┤
│   Service Layer (business)      │  ← Business logic (future)
├─────────────────────────────────┤
│   Repository Layer (data)       │  ← CRUD operations (future)
├─────────────────────────────────┤
│   Model Layer (database)        │  ← ORM definitions (future)
└─────────────────────────────────┘
```

### Dependencies (pyproject.toml)

```toml
[project]
name = "sit-copilot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.32",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "pytest-mock>=3.12",
    "pytest-asyncio>=0.25.1",  # Critical: asyncio_mode = "auto" required
    "httpx>=0.26",             # For ASGITransport
    "ruff>=0.8",
    "ty>=0.11",
]

# Tool configurations
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"  # REQUIRED for FastAPI async tests
addopts = [
    "-v",
    "--cov=app",
    "--cov-report=term-missing",
]

[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "UP",     # pyupgrade
    "ASYNC",  # flake8-async (important for FastAPI)
]
ignore = ["E501"]  # formatter handles

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports

[tool.ty]
strict = true
disallow_untyped_defs = true

[[tool.ty.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

### Pytest Fixture Architecture

**Modern 2025 approach**: Use `httpx.AsyncClient` with `ASGITransport`

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
```

### Health Endpoint Design

```python
# app/api/v4/health.py
from fastapi import APIRouter, status
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])

@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=HealthResponse,
)
async def get_health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy")

# app/schemas/health.py
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
```

### Implementation Plan

| Step | Task | Dependencies |
|------|------|--------------|
| 1 | Initialize pyproject.toml with uv | None |
| 2 | Create directory structure | 1 |
| 3 | Create core/config.py (settings) | 2 |
| 4 | Create schemas/health.py | 2 |
| 5 | Create main.py (FastAPI app) | 2, 3 |
| 6 | Create api/v4/health.py (route) | 4, 5 |
| 7 | Write tests/conftest.py (fixtures) | 5 |
| 8 | Write tests/api/test_health.py | 6, 7 |
| 9 | Run pytest (TDD: should pass) | 8 |
| 10 | Verify /api/v4/health returns 200 | 9 |

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| pytest-asyncio compatibility | Medium | Use >=0.24 for Python 3.11, configure with `asyncio_mode = auto` |
| AsyncClient vs TestClient | Low | AsyncClient is 2025 best practice, use ASGITransport |
| ruff + ty compatibility | Low | Both from Astral, work well together |

---

## Sprint1 Settings API & SQLite Persistence (2026-02-20)

### Project: User Settings API with SQLite

**Goal**: Implement SQLite persistence and user settings API (GET/POST /api/v4/settings/me) as foundation for future features.

### Scope
- **Include**: SQLAlchemy setup, DB session management, users table, settings API, Pydantic schemas, common error responses
- **Exclude**: Azure connection, LLM, lecture functionality

### Success Criteria
- pytest passes
- GET/POST /api/v4/settings/me works
- Validation errors return 400
- Response JSON matches specification

### Directory Structure (Updated)

```
sit-copilot/
├── app/
│   ├── main.py                    # FastAPI app
│   ├── api/
│   │   └── v4/
│   │       ├── __init__.py
│   │       ├── health.py          # (existing)
│   │       └── settings.py        # NEW: Settings API endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py              # (existing, add database_url)
│   ├── db/
│   │   ├── __init__.py            # NEW: Database infrastructure
│   │   ├── base.py                # NEW: SQLAlchemy Base
│   │   └── session.py             # NEW: Async session dependency
│   ├── models/
│   │   ├── __init__.py            # NEW: ORM models
│   │   └── user_settings.py       # NEW: UserSettings model
│   ├── services/
│   │   ├── __init__.py            # NEW: Business logic layer
│   │   └── settings_service.py    # NEW: SettingsService
│   └── schemas/
│       ├── __init__.py
│       ├── health.py              # (existing)
│       └── settings.py            # NEW: Settings request/response schemas
│
├── tests/
│   ├── conftest.py                # (existing, add db fixture)
│   ├── api/
│   │   └── v4/
│   │       ├── __init__.py
│   │       ├── test_health.py     # (existing)
│   │       └── test_settings.py   # NEW: Settings API tests
│   └── unit/
│       ├── __init__.py
│       ├── schemas/
│       │   └── test_settings_schemas.py   # NEW: Schema validation tests
│       └── services/
│           └── test_settings_service.py   # NEW: Service layer tests
│
└── pyproject.toml                 # (add dependencies)
```

### Data Model

#### UserSettings Table

```python
# app/models/user_settings.py
from sqlalchemy import String, DateTime, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_settings_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

**Design Rationale**:
- One row per user (simpler queries, better performance)
- JSON column for flexible settings (theme, notifications, language, etc.)
- Unique constraint on user_id (prevents duplicates)
- Timestamps for auditing

**CRITICAL: JSON Mutation Tracking**
When mutating JSON fields, always call `flag_modified()` to ensure SQLAlchemy tracks changes:
```python
from sqlalchemy.orm.attributes import flag_modified

user_settings.settings = {"theme": "dark"}
flag_modified(user_settings, "settings")  # REQUIRED
```
Without `flag_modified()`, changes may not be persisted to the database.

### DB Session Management

```python
# app/db/session.py
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(
    "sqlite+aiosqlite:///./sit_copilot.db",
    echo=False,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # REQUIRED: Prevents lazy loading errors
)

async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for database session with auto-commit."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()  # Auto-commit on success
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Key Configuration**:
- `expire_on_commit=False` prevents detached instance errors
- **Auto-commit on success** (simpler route handlers)
- Auto-rollback on exception
- Explicit session close in finally block

### Service Layer Architecture

```python
# app/services/settings_service.py
from typing import Protocol

class SettingsService(Protocol):
    """Interface for settings operations."""

    async def get_my_settings(self, user_id: str) -> SettingsResponse:
        """Get user settings. Returns empty dict if not found."""
        ...

    async def upsert_my_settings(
        self, user_id: str, request: SettingsUpsertRequest
    ) -> SettingsResponse:
        """Create or update user settings."""
        ...
```

**Design Pattern**:
- Protocol interface for testability
- Implementation separated from interface
- Business logic in service, not in routes

### API Contract

#### GET /api/v4/settings/me

**Response (200)**:
```json
{
    "user_id": "user123",
    "settings": {
        "theme": "dark",
        "notifications_enabled": true,
        "language": "ja"
    },
    "updated_at": "2026-02-20T12:00:00Z"
}
```

#### POST /api/v4/settings/me

**Request**:
```json
{
    "settings": {
        "theme": "light",
        "new_field": "value"
    }
}
```

**Response (200)**: Same as GET

**Validation Error (400)**:
```json
{
    "detail": [
        {
            "type": "dict_type",
            "loc": ["body", "settings"],
            "msg": "Input should be a valid dictionary",
        }
    ]
}
```

### Dependencies to Add

```toml
[project]
dependencies = [
    "fastapi>=0.110",
    "pydantic-settings>=2.13.1",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0",  # NEW: Async support
    "aiosqlite>=0.21.0",         # NEW: SQLite async driver (Feb 2025)
]
```

### TDD Implementation Plan

| Step | Task | Dependencies | Test Type |
|------|------|--------------|-----------|
| 1 | Add dependencies (sqlalchemy, aiosqlite) | None | - |
| 2 | Create db/base.py, db/session.py | 1 | Unit |
| 3 | Create models/user_settings.py | 2 | Unit |
| 4 | Create schemas/settings.py | None | Unit (Pydantic) |
| 5 | Create test_settings_schemas.py (failing) | 4 | Unit |
| 6 | Implement schemas/settings.py | 5 | Unit |
| 7 | Create test_settings_service.py (failing) | 3, 6 | Unit |
| 8 | Implement services/settings_service.py | 7 | Unit |
| 9 | Create test_settings.py API tests (failing) | 8 | Integration |
| 10 | Implement api/v4/settings.py routes | 9 | Integration |
| 11 | Register router in main.py | 10 | Integration |
| 12 | Run pytest -v (all green) | 11 | E2E |
| 13 | Run ruff check . && ty check app/ | 12 | Quality |

### Common Error Response Schema

```python
# app/schemas/error.py (optional, for consistency)
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    detail: list[dict[str, Any]] | str
```

FastAPI provides this automatically via Pydantic validation, but explicit schema enables documentation.

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| aiosqlite compatibility | Medium | Use >=0.20, verify with test suite first |
| JSON column limitations | Low | SQLite supports JSON operations; fallback to TEXT if needed |
| Async session leaks | High | Use dependency injection, context managers, pytest fixtures |
| Migration complexity | Medium | Use Alembic for production; simple CREATE TABLE for demo |
| Test database state | Medium | Use in-memory SQLite (`:memory:`) for tests |

### Testing Strategy

#### Unit Tests
- **Schema validation**: Pydantic model tests
- **Service layer**: Mock DB session, test business logic

#### Integration Tests
- **API endpoints**: Use AsyncClient with ASGITransport
- **Database operations**: Use in-memory SQLite fixture

```python
# tests/conftest.py (updated)
@pytest.fixture
async def db_session():
    """In-memory SQLite for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
```

### Detailed File Structure

```
app/
├── db/
│   ├── __init__.py
│   ├── base.py              # DeclarativeBase import
│   └── session.py           # engine, AsyncSessionFactory, get_db_session
├── models/
│   ├── __init__.py
│   └── user_settings.py     # UserSettings ORM model
├── services/
│   ├── __init__.py
│   └── settings_service.py  # SettingsService Protocol + implementation
├── schemas/
│   ├── __init__.py
│   ├── health.py            # (existing)
│   └── settings.py          # SettingsUpsertRequest, SettingsResponse
└── api/v4/
    ├── __init__.py
    ├── health.py            # (existing)
    └── settings.py          # GET/POST /settings/me routes
```

### Service Layer Implementation Details

```python
# app/services/settings_service.py (implementation example)
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from app.models.user_settings import UserSettings
from app.schemas.settings import SettingsUpsertRequest, SettingsResponse

class SqlAlchemySettingsService:
    """SQLAlchemy implementation of SettingsService."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_my_settings(self, user_id: str) -> SettingsResponse:
        result = await self._db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        user_settings = result.scalar_one_or_none()
        if user_settings:
            return SettingsResponse(
                user_id=user_settings.user_id,
                settings=user_settings.settings,
                updated_at=user_settings.updated_at,
            )
        return SettingsResponse(user_id=user_id, settings={}, updated_at=None)

    async def upsert_my_settings(
        self, user_id: str, request: SettingsUpsertRequest
    ) -> SettingsResponse:
        result = await self._db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        user_settings = result.scalar_one_or_none()

        if user_settings:
            # CRITICAL: Must use flag_modified() for JSON mutations
            user_settings.settings = request.settings
            flag_modified(user_settings, "settings")
        else:
            user_settings = UserSettings(user_id=user_id, settings=request.settings)
            self._db.add(user_settings)

        await self._db.commit()
        await self._db.refresh(user_settings)
        return SettingsResponse(
            user_id=user_settings.user_id,
            settings=user_settings.settings,
            updated_at=user_settings.updated_at,
        )
```

**IMPORTANT**: When mutating JSON fields, always call `flag_modified()` to ensure SQLAlchemy tracks the change. Without this, changes may not be persisted.

### API Routes Implementation

```python
# app/api/v4/settings.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.settings import SettingsUpsertRequest, SettingsResponse
from app.services.settings_service import SqlAlchemySettingsService

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/me", status_code=status.HTTP_200_OK, response_model=SettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Get current user's settings."""
    # TODO: Replace with actual user_id from auth
    user_id = "demo_user"
    service = SqlAlchemySettingsService(db)
    return await service.get_my_settings(user_id)

@router.post("/me", status_code=status.HTTP_200_OK, response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpsertRequest,
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Update current user's settings."""
    # TODO: Replace with actual user_id from auth
    user_id = "demo_user"
    service = SqlAlchemySettingsService(db)
    return await service.upsert_my_settings(user_id, request)
```

### Test Cases to Cover

#### Schema Tests (`tests/unit/schemas/test_settings_schemas.py`)
- [x] SettingsUpsertRequest accepts valid dict
- [x] SettingsUpsertRequest rejects non-dict
- [x] SettingsUpsertRequest rejects extra fields (extra="forbid")
- [x] SettingsResponse serializes correctly

#### Service Tests (`tests/unit/services/test_settings_service.py`)
- [x] get_my_settings returns empty dict when user not found
- [x] get_my_settings returns existing settings
- [x] upsert_my_settings creates new user settings
- [x] upsert_my_settings updates existing settings
- [x] upsert_my_settings updates updated_at timestamp

#### API Tests (`tests/api/v4/test_settings.py`)
- [x] GET /api/v4/settings/me returns 200
- [x] GET /api/v4/settings/me returns JSON with correct structure
- [x] POST /api/v4/settings/me creates settings
- [x] POST /api/v4/settings/me updates settings
- [x] POST /api/v4/settings/me returns 400 for invalid JSON
- [x] GET after POST returns updated settings

---

## Sprint2 Procedure QA Minimal Planning (2026-02-20)

### Project: Procedure QA Minimal (Rooted Answers First)

**Goal**: Deliver a minimal F2 backend slice that fixes retrieval/grounding contracts before real Azure integrations.

### Scope
- **Include**: `POST /api/v4/procedure/ask`, retrieval interface, answerer interface, `qa_turns` persistence, rootless-answer prohibition logic
- **Exclude**: Azure AI Search real connection, Azure OpenAI real connection, UI

### Constraints
- TDD-first
- Retriever and answerer start as Fake implementations
- Return fallback when `sources` is empty
- Always return `confidence`, `sources`, and `action_next`

### Success Criteria
- `pytest` passes
- Evidence-backed input returns answer with `sources`
- No-evidence input returns fallback
- Both paths persist to `qa_turns`

### Planned Architecture

```
POST /api/v4/procedure/ask
  -> ProcedureQAService
     -> ProcedureRetrievalService (Fake first)
     -> Rootless guard (if no sources => fallback)
     -> ProcedureAnswererService (Fake first, only when sources exist)
     -> QATurn persistence (feature=procedure_qa)
```

### Planned Deliverables

- Research:
  - `.claude/docs/research/procedure-qa-minimal-codebase.md`
  - `.claude/docs/research/procedure-qa-minimal.md`
  - `.claude/docs/research/procedure-qa-minimal-plan.md`
- Code targets (implementation phase):
  - `app/api/v4/procedure.py`
  - `app/schemas/procedure.py`
  - `app/models/qa_turn.py`
  - `app/services/procedure_retrieval_service.py`
  - `app/services/procedure_answerer_service.py`
  - `app/services/procedure_qa_service.py`

---

## Sprint2 Procedure QA Minimal Implementation (2026-02-20)

### Implemented Scope

- Added `POST /api/v4/procedure/ask`
- Added retrieval service interface + fake implementation
- Added answerer service interface + fake implementation
- Added `qa_turns` persistence model and write path
- Added deterministic rootless-answer prohibition (`sources == []` => fallback)

### Delivered Files

- API
  - `app/api/v4/procedure.py`
  - `app/api/v4/__init__.py` (procedure export)
  - `app/main.py` (router registration)
- Schemas
  - `app/schemas/procedure.py`
  - `app/schemas/__init__.py` (procedure schema exports)
- Models
  - `app/models/qa_turn.py`
  - `app/models/__init__.py` (`QATurn` export)
- Services
  - `app/services/procedure_retrieval_service.py`
  - `app/services/procedure_answerer_service.py`
  - `app/services/procedure_qa_service.py`
  - `app/services/__init__.py` (procedure service exports)
- Tests
  - `tests/api/v4/test_procedure.py`
  - `tests/unit/schemas/test_procedure_schemas.py`
  - `tests/unit/services/test_procedure_qa_service.py`

### Verification Results

- `uv run pytest -q` -> pass (`24 passed`)
- `uv run mypy .` -> pass
- `uv run ty check app/` -> pass
- `uv run ruff check app tests` -> pass
- `uv run ruff check .` -> fail due existing `.claude/hooks` / `.claude/skills` lint debt outside Sprint2 scope

### Outcome

Sprint2 minimal success criteria were met:
- Evidence query returns answer with `sources`
- No-evidence query returns non-empty `fallback`
- `qa_turns` is persisted in both paths
- API contract always includes `confidence`, `sources`, and `action_next`

### Post-Review Hardening (Medium Findings Fixed)

- Added token auth dependency for procedure endpoint (`X-Procedure-Token`).
- Refactored route wiring to dependency-based service injection (no direct fake instantiation in handler body).
- Externalized retrieval/fallback knobs into settings and passed into service constructor.
- Added `query` max-length + blank normalization validation.
- Expanded tests for invalid `lang_mode` and persisted metadata assertions (`citations_json`, `latency_ms`, fallback-path flags).

---

## Sprint3 F1 Speech Event Persistence + Subtitle Display Planning (2026-02-20)

### Project: F1 Step 3 (Speech Event Save + Subtitle Display Contract)

**Goal**: Implement SPEC step 3 by adding lecture session start and finalized speech event persistence, with API acknowledgement support for subtitle display continuity.

### Scope

- **Include**:
  - `POST /api/v4/lecture/session/start`
  - `POST /api/v4/lecture/speech/chunk`
  - `lecture_sessions` table/model
  - `speech_events` table/model
  - Validation for consent, active session, timing and confidence ranges
- **Exclude**:
  - OCR ingestion (`/lecture/visual/event`)
  - 30-second summary generation
  - Finalize/index generation flow
  - Frontend implementation
  - Real Azure Speech token issuance

### Planned Architecture

```
POST /api/v4/lecture/session/start
  -> LectureLiveService.start_session()
     -> create LectureSession(status="active")

POST /api/v4/lecture/speech/chunk
  -> LectureLiveService.ingest_speech_chunk()
     -> validate active session + final-event constraints
     -> persist SpeechEvent
     -> return ingestion acknowledgement
```

### Planned Deliverables

- Research:
  - `.claude/docs/research/sprint3-f1-speech-events-and-subtitles-codebase.md`
  - `.claude/docs/research/sprint3-f1-speech-events-and-subtitles.md`
  - `.claude/docs/research/sprint3-f1-speech-events-and-subtitles-plan.md`
- Code targets (implementation phase):
  - `app/api/v4/lecture.py`
  - `app/schemas/lecture.py`
  - `app/models/lecture_session.py`
  - `app/models/speech_event.py`
  - `app/services/lecture_live_service.py`
  - `tests/api/v4/test_lecture.py`
  - `tests/unit/schemas/test_lecture_schemas.py`
  - `tests/unit/services/test_lecture_live_service.py`

---

## Sprint3 F1 Speech Event Persistence + Subtitle Display Implementation (2026-02-20)

### Implemented Scope

- Added `POST /api/v4/lecture/session/start`
- Added `POST /api/v4/lecture/speech/chunk`
- Added `lecture_sessions` persistence model
- Added `speech_events` persistence model
- Added lecture live service for session creation + speech ingestion
- Added schema-level constraints for consent, ROI bounds, timing, confidence, and finalized-event-only ingestion

### Delivered Files

- API
  - `app/api/v4/lecture.py`
  - `app/api/v4/__init__.py` (lecture export)
  - `app/main.py` (lecture router registration)
- Schemas
  - `app/schemas/lecture.py`
  - `app/schemas/__init__.py` (lecture schema exports)
- Models
  - `app/models/lecture_session.py`
  - `app/models/speech_event.py`
  - `app/models/__init__.py` (lecture model exports)
- Services
  - `app/services/lecture_live_service.py`
  - `app/services/__init__.py` (lecture service exports)
- Tests
  - `tests/unit/schemas/test_lecture_schemas.py`
  - `tests/unit/services/test_lecture_live_service.py`
  - `tests/api/v4/test_lecture.py`
  - `tests/conftest.py` (model metadata import updates)
- Shared hardening
  - `app/core/errors.py` (JSON-safe serialization of validation `details`)

### Verification Results

- `uv run ruff check app/models` -> pass
- `uv run ty check app/models` -> pass
- `uv run ruff check app/schemas app/services` -> pass
- `uv run ty check app/schemas app/services` -> pass
- `uv run ruff check app/api/v4 app/main.py` -> pass
- `uv run ty check app/api/v4 app/main.py` -> pass
- `uv run ruff check tests` -> pass
- `uv run ty check tests` -> pass
- `uv run pytest tests/unit/schemas/test_lecture_schemas.py tests/unit/services/test_lecture_live_service.py tests/api/v4/test_lecture.py -v` -> pass (`15 passed`)
- `uv run ty check app/` -> pass
- `uv run pytest -v` -> pass (`42 passed`)
- `uv run ruff check .` -> fail due existing `.claude/hooks` / `.claude/skills` lint debt outside Sprint3 scope
- `uv run ruff format --check .` -> fail due existing `.claude/*` + pre-existing non-Sprint3 files requiring formatting

### Outcome

Sprint3 step-3 success criteria were met:
- Speech events are persisted to `speech_events`.
- Session lifecycle start is persisted to `lecture_sessions`.
- Subtitle-display backend contract is provided via deterministic speech chunk acknowledgement response.
- Scope is kept to step 3 only (no OCR/summary/finalize implementation).

### Post-Review Hardening (High/Medium Findings Fixed)

- Added lecture token auth guard (`X-Lecture-Token`) for all `/api/v4/lecture/*` write endpoints.
- Added request user context dependency (`X-User-Id`) and removed hardcoded service user default.
- Enforced session ownership in ingestion query (`session_id + user_id`) to prevent cross-user writes.
- Added ROI geometry validation (`x1 < x2` and `y1 < y2`) in lecture start schema.
- Added API integration test for inactive-session `409` branch and auth-missing `401` branch.
- Added service test for cross-user session write rejection.
- Re-verified full suite after hardening (`uv run pytest -v` -> `46 passed`).

---

## Azure Provisioning for SIT Copilot MVP (2026-02-20)

### Goal

Provision the minimum Azure resources required by `docs/SPEC.md` section 7 and document a reproducible CLI-based setup path for integration work.

### Provisioned Environment

- Subscription: `Azure サブスクリプション 1`
- Region: `japaneast`
- Resource group: `rg-sitcopilot-dev-02210594`
- Resources:
  - Key Vault: `kvsitc02210594`
  - Storage Account: `stsitc02210594`
  - Azure AI Search: `srchsitc02210594`
  - Azure AI Speech: `speech-sitc-02210594`
  - Azure AI Vision: `vision-sitc-02210594`
  - Azure OpenAI: `aoai-sitc-02210594`
  - Application Insights: `appi-sitc-02210594`

### Provisioning Notes

- Azure resource providers were registered before provisioning:
  - `Microsoft.KeyVault`
  - `Microsoft.CognitiveServices`
  - `Microsoft.Search`
  - `Microsoft.Storage`
  - `Microsoft.Insights`
  - `Microsoft.OperationalInsights`
- Provisioning was executed via Azure CLI from Codex terminal.
- Key Vault was created in RBAC mode; secret write capability was enabled by assigning `Key Vault Secrets Officer` at vault scope.
- Generated local bootstrap file: `.env.azure.generated` (contains connection values and keys for development).
- Stored secrets in Key Vault:
  - `azure-speech-key`
  - `azure-vision-key`
  - `azure-search-key`
  - `azure-storage-key`
  - `azure-openai-key`
  - `applicationinsights-connection-string`
- Removed two failed/empty trial resource groups and retained only the active environment resource group.

### Security and Operations Constraints

- `.env.azure.generated` is sensitive and must not be committed to remote repositories.
- Application runtime should prefer Key Vault and environment-variable injection over hardcoded values.
- Rotate service keys before external demo/release and when sharing environments.

---

## F4 Lecture QA Implementation (2026-02-21)

### Project: F4 Lecture QA (講義後QA)

**Goal**: Implement lecture QA pipeline that answers questions based on actual lecture content (speech, board, slides) with local BM25 search and Azure OpenAI verification.

### Scope
- **Include**:
  - `POST /api/v4/lecture/qa/index/build` - Build BM25 index from SpeechEvents
  - `POST /api/v4/lecture/qa/ask` - Ask question with source-only/source-plus-context modes
  - `POST /api/v4/lecture/qa/followup` - Follow-up questions with context resolution
  - BM25 local search (rank-bm25 library)
  - Azure OpenAI answer generation
  - LLM-based Verifier for citation validation
  - QATurn persistence (feature=lecture_qa)

- **Exclude**:
  - Azure AI Search integration (future F4.3)
  - Real-time OCR integration (handled by F1)

### Module Structure

```
app/
├── api/v4/lecture_qa.py                    # /lecture/qa/index/build, /lecture/qa/ask
├── schemas/lecture_qa.py                   # request/response/citation/index schemas
├── services/
│   ├── lecture_qa_service.py               # Orchestrator: retrieve -> answer -> verify -> persist
│   ├── lecture_retrieval_service.py        # BM25 retrieval + context expansion modes
│   ├── lecture_index_service.py            # Build/rebuild BM25 corpus from SpeechEvent
│   ├── lecture_answerer_service.py         # Azure OpenAI grounded answer generation
│   ├── lecture_verifier_service.py         # Azure OpenAI citation/claim verification
│   ├── lecture_followup_service.py         # Follow-up rewrite + history packing
│   └── lecture_bm25_store.py               # In-memory per-session BM25 cache + locks
└── core/config.py                          # lecture_qa_* and azure_openai_* settings
```

### Data and Pipeline Design

- `LectureSession.qa_index_built` is the canonical DB flag to indicate index availability.
- Index corpus is built from `speech_events` with `is_final=true`, ordered by `start_ms`.
- Primary source unit is one `SpeechEvent` row (`chunk_id = speech_event.id`), preserving timestamp precision for citations.
- Retrieval modes:
  - `source-only`: return top-k matched chunks only.
  - `source-plus-context`: expand each hit with neighboring chunks (window by chunk-count or milliseconds), deduplicate by `chunk_id`, and mark which chunk is the direct hit.
- QA turn history is persisted in existing `qa_turns` table with `feature=lecture_qa`.

### API Contract (v4)

- `POST /api/v4/lecture/qa/index/build`
  - Ensures ownership (`session_id + user_id`), builds/rebuilds BM25 index, sets `qa_index_built=true`.
- `POST /api/v4/lecture/qa/ask`
  - Performs follow-up resolution, retrieval, answering, verification, and history persistence.
  - Supports `retrieval_mode` = `source-only | source-plus-context`.

### Verification Guardrails

- If retrieval returns no chunks: deterministic low-confidence fallback (no hallucinated answer).
- Verifier validates each cited claim against provided source snippets.
- If verifier rejects support:
  - First pass: attempt constrained repair (answer only from verified chunks).
  - If still unsupported: return fallback with low confidence and keep rejected citations out of response.

### Async/Concurrency

- `rank-bm25` scoring/index construction is CPU-bound and must run via `asyncio.to_thread(...)`.
- Per-session `asyncio.Lock` prevents concurrent index-build races.
- DB IO remains async via SQLAlchemy 2.0 `AsyncSession`; long-running LLM calls are timeout-bound.

---

## Implementation Plan

### Patterns & Approaches

| Pattern | Purpose | Notes |
|---------|---------|-------|
| Agent Teams | Parallel work with inter-agent communication | /startproject, /team-implement, /team-review |
| Subagents | Isolated tasks returning results | External research, Codex consultation, implementation |
| Skill Pipeline | `/startproject` → `/team-implement` → `/team-review` | Separation of concerns across skills |

### Libraries & Roles

| Library | Role | Version | Notes |
|---------|------|---------|-------|
| Codex CLI | Planning, design, complex code | gpt-5.3-codex | Architecture, planning, debug, complex implementation |
| Gemini CLI | Multimodal file reading | gemini-3-pro | PDF/video/audio/image extraction ONLY |
| FastAPI | Web framework | >=0.115 | Async-first, type-safe |
| pytest | Testing | >=8.0 | TDD with async support |
| httpx | Async HTTP client | >=0.28 | For testing FastAPI with ASGITransport |

### Key Decisions

| Decision | Rationale | Alternatives Considered | Date |
|----------|-----------|------------------------|------|
| Gemini role expanded to codebase analysis + research + multimodal | Gemini CLI has native 1M context; Claude Code is 200K; delegate large-context tasks to Gemini | Keep Claude for codebase analysis (requires 1M Beta) | 2026-02-19 |
| All subagents default to Opus | 200K context makes quality of reasoning more important than context size; Opus provides better output | Sonnet (cheaper but 200K same as Opus, weaker reasoning) | 2026-02-19 |
| Agent Teams default model changed to Opus | Consistent with subagent model selection; better reasoning for parallel tasks | Sonnet (cheaper) | 2026-02-19 |
| Claude Code context corrected to 200K | 1M is Beta/pay-as-you-go only; most users have 200K; design must work for common case | Assume 1M (only works for Tier 4+ users) | 2026-02-19 |
| Subagent delegation threshold lowered to ~20 lines | 200K context requires more aggressive context management | 50 lines (was based on 1M assumption) | 2026-02-19 |
| Codex role unchanged (planning + complex code) | Codex excels at deep reasoning for both design and implementation | Keep Codex advisory-only | 2026-02-17 |
| Codex project skills include startproject/team-implement/team-review bridges | Enables Claude-style `/startproject`, `/team-implement`, `/team-review` workflow from Codex while keeping `.claude/skills/*` as source of truth | Duplicate full skill content under `.codex/skills`, keep commands Claude-only | 2026-02-20 |
| Codex project skills include checkpointing bridge plus `/checkpoining` alias | Enables session checkpoint workflow from Codex and keeps typo-tolerant command compatibility while reusing `.claude/skills/checkpointing` as source of truth | Keep checkpointing Claude-only, no alias support | 2026-02-20 |
| Codex skills rewritten to remove Claude runtime dependencies | Ensures `/startproject`, `/team-implement`, `/team-review`, `/checkpointing` can run with Codex + Gemini only (no Agent Teams, Task tool, subagents) | Keep bridge-only delegation to `.claude/skills/*` | 2026-02-20 |
| /startproject split into 3 skills | Separation of Plan/Implement/Review gives user control gates | Single monolithic skill | 2026-02-08 |
| Agent Teams for Research ↔ Design | Bidirectional communication enables iterative refinement | Sequential subagents (old approach) | 2026-02-08 |
| Agent Teams for parallel implementation | Module-based ownership avoids file conflicts | Single-agent sequential implementation | 2026-02-08 |
| FastAPI AsyncClient for testing (2025) | httpx.AsyncClient with ASGITransport is modern best practice for async FastAPI tests | TestClient (legacy), starlette TestClient | 2026-02-21 |
| API versioning with /api/v4/ | Explicit versioning allows breaking changes without breaking existing clients | /api/v1/ (arbitrary), no versioning (brittle) | 2026-02-21 |
| Layered architecture: API → Service → Repository | Clear separation of concerns enables independent testing and evolution | Flat structure (harder to scale), MVC (less clear for APIs) | 2026-02-21 |
| User settings persisted in SQLite with JSON column | Flexible, schema-less user preferences while keeping one row per user; SQLite JSON functions remain available | Normalized key-value table (more joins), TEXT blob without JSON type | 2026-02-20 |
| SQLAlchemy 2.0 async stack for DB access | Matches FastAPI async flow and keeps one consistent ORM access pattern | Sync SQLAlchemy (thread pool overhead), raw sqlite3 (less abstraction) | 2026-02-20 |
| Settings API boundary: API → Service (upsert/get) | Keeps HTTP details out of business logic and enables isolated unit tests for settings behavior | Direct DB calls in route handlers | 2026-02-20 |
| Settings upsert creates missing `users` row lazily | Keeps router thin and guarantees `users` + `user_settings` consistency in demo single-replica SQLite without separate signup flow | Require pre-provisioned user row before POST `/settings/me` | 2026-02-20 |
| Validation errors normalized to common 400 schema | Aligns API with project-wide error contract and success criteria (`400` for invalid input with structured `error` payload) | Keep FastAPI default 422 `detail` response | 2026-02-20 |
| Prioritize F2 Procedure QA as the next feature after backend/settings foundation | Matches `docs/SPEC.md` implementation order step 2 and enables an early source-grounded demo path before higher-latency F1 realtime pipelines | Start F1 speech/OCR ingestion first | 2026-02-20 |
| Sprint2 starts with fake retriever/answerer interfaces before Azure wiring | Freezes RAG boundaries and response contract early, while keeping implementation deterministic for TDD | Implement real Azure integrations first (higher coupling and slower tests) | 2026-02-20 |
| Procedure rootless answers are blocked by deterministic guard (`sources == []` => fallback) | Enforces evidence-first safety rule from spec and prevents unsupported answers in MVP | Allow answerer output without sources and trust model self-restraint | 2026-02-20 |
| Procedure QA persistence uses shared `qa_turns` with `feature=procedure_qa` and serialized `sources` | Keeps lecture/procedure QA telemetry unified and future verifier compatibility intact | Separate procedure-specific history table | 2026-02-20 |
| Procedure endpoint enforces header token auth and DI-based service composition | Addresses review findings by reducing anonymous write risk and avoiding route-level implementation coupling | Keep route-level fake service instantiation and no auth in minimal mode | 2026-02-20 |
| Procedure query limits and fallback/retrieval knobs are settings-driven | Improves operational tunability and protects against unbounded payload growth | Keep hardcoded literals in service and schema | 2026-02-20 |
| Sprint3 F1 is backend-first and persists finalized subtitle events only | Aligns with SPEC (frontend displays partial subtitles, backend stores finalized events) and keeps ingestion deterministic | Persist partial + final events together in Sprint3 | 2026-02-20 |
| Sprint3 endpoint scope is limited to session start + speech chunk | Matches implementation order step 3 and avoids coupling to OCR/summary/finalize before contracts are stable | Build full F1 pipeline in one sprint | 2026-02-20 |
| Subtitle display support is defined as ingestion acknowledgement contract in backend | Repository currently has no frontend code; acknowledgement keeps client rendering decoupled while preserving DB traceability | Add subtitle polling/read endpoint in Sprint3 | 2026-02-20 |
| Validation error details are JSON-encoded before error response serialization | Prevents `ValueError` objects inside Pydantic `ctx` from breaking error response generation | Keep raw `exc.errors()` payload | 2026-02-20 |
| Lecture write endpoints require token auth and user context headers | Fixes high-risk anonymous write surface and prepares multi-user ownership boundary | Keep lecture endpoints unauthenticated in Sprint3 | 2026-02-20 |
| Lecture speech ingestion checks session ownership (`session_id + user_id`) | Prevents cross-user session write contamination in shared environments | Query by `session_id` only | 2026-02-20 |
| Lecture ROI validation enforces geometry ordering | Prevents invalid inverted regions from propagating to downstream OCR pipeline | Validate non-negative coordinates only | 2026-02-20 |
| Lecture QA uses `SpeechEvent` rows as BM25 chunk units and keeps index in process-local cache keyed by `session_id` | Reuses finalized subtitle data without schema churn and keeps retrieval latency low for active sessions | Persist separate lecture chunk index tables first | 2026-02-20 |
| Lecture QA keeps existing orchestration pattern (`retrieve -> answer -> verify`) with Azure OpenAI for answering and citation validation | Aligns with procedure QA structure and adds explicit groundedness gate before response | Single-pass answer generation without verifier step | 2026-02-20 |
| Lecture follow-up handling rewrites question to standalone query using recent `QATurn` context before retrieval | Improves retrieval recall for pronoun/ellipsis follow-ups while keeping source grounding explicit | Retrieve directly on raw follow-up question only | 2026-02-20 |
| Azure MVP resources are provisioned via CLI in `japaneast` with low-cost/default SKUs (`Speech F0`, `ComputerVision F0`, `Search free`, `OpenAI S0`) | Unblocks integration quickly while controlling cost and preserving reproducibility | Manual portal-only setup per developer | 2026-02-20 |
| Azure secrets are stored in Key Vault and mirrored to local `.env.azure.generated` for bootstrap | Keeps a secure central source while enabling immediate local integration testing | Local `.env` only, or Key Vault-only with full managed identity wiring first | 2026-02-20 |
| Key Vault secret operations use RBAC role assignment (`Key Vault Secrets Officer`) | Vault was created in RBAC mode; role assignment is the compatible path for secret writes | Recreate vault in access-policy mode | 2026-02-20 |

---

## Sprint4 F4 Lecture QA Architecture (2026-02-21)

### Project: F4 Lecture QA (講義後QA)

**Goal**: Implement lecture-based question answering using BM25 local search + Azure OpenAI for answer generation and citation verification.

### Scope

- **Include**:
  - `POST /api/v4/lecture/qa/ask` - Question answering with follow-up support
  - `POST /api/v4/lecture/qa/index/build` - Search index builder from SpeechEvents
  - Local BM25 search using `rank-bm25` library
  - Two retrieval modes: `source-only` and `source-plus-context`
  - LLM-based Verifier for citation validation
  - Follow-up question handling with conversation context
- **Exclude**:
  - Azure AI Search integration (future)
  - Real-time OCR integration (handled by F1)

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         API Layer                                    │
│  POST /api/v4/lecture/qa/index/build                                │
│  POST /api/v4/lecture/qa/ask                                         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Service Layer                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ LectureQAService │  │ LectureIndexSvc  │  │  LectureFollowup │  │
│  │   (Orchestrator) │  │  (Index Builder) │  │     Service      │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
│           │                     │                      │             │
│           ▼                     ▼                      ▼             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ LectureRetrieval │  │  LectureAnswerer │  │ LectureVerifier  │  │
│  │    Service       │  │     Service      │  │     Service      │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│           │                     │                      │             │
│           ▼                     ▼                      ▼             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  BM25Store       │  │   Azure OpenAI   │  │   Azure OpenAI   │  │
│  │ (In-Memory Cache)│  │   (Answer Gen)   │  │  (Verification)  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Data Layer                                     │
│  LectureSession (qa_index_built flag)                               │
│  SpeechEvent (text chunks with timestamps)                          │
│  QATurn (conversation history with feature=lecture_qa)              │
└─────────────────────────────────────────────────────────────────────┘
```

### Module Structure

| Module | File | Responsibility |
|--------|------|----------------|
| API Routes | `app/api/v4/lecture_qa.py` | HTTP endpoints, auth, DI wiring |
| Schemas | `app/schemas/lecture_qa.py` | Request/response models |
| QA Orchestrator | `app/services/lecture_qa_service.py` | retrieve → answer → verify → persist |
| Index Builder | `app/services/lecture_index_service.py` | SpeechEvents → BM25 index |
| BM25 Cache | `app/services/lecture_bm25_store.py` | In-memory index storage with lock |
| Retrieval | `app/services/lecture_retrieval_service.py` | BM25 search + context expansion |
| Follow-up | `app/services/lecture_followup_service.py` | History load + query rewrite |
| Answerer | `app/services/lecture_answerer_service.py` | Azure OpenAI answer generation |
| Verifier | `app/services/lecture_verifier_service.py` | Citation validation |

### Key Interfaces

```python
# LectureIndexService
class LectureIndexService(Protocol):
    async def build_index(
        self, session_id: str, user_id: str, rebuild: bool = False
    ) -> LectureQAIndexBuildResponse: ...

# LectureRetrievalService
class LectureRetrievalService(Protocol):
    async def retrieve(
        self,
        session_id: str,
        query: str,
        mode: RetrievalMode,  # "source-only" | "source-plus-context"
        top_k: int,
        context_window: int,  # Number of neighboring chunks
    ) -> list[LectureSource]: ...

# LectureFollowupService
class LectureFollowupService(Protocol):
    async def resolve_query(
        self, session_id: str, user_id: str, question: str, history_turns: int
    ) -> FollowupResolution:  # standalone_query + history context
        ...

# LectureAnswererService
class LectureAnswererService(Protocol):
    async def answer(
        self, question: str, lang_mode: str, sources: list[LectureSource], history: str
    ) -> LectureAnswerDraft: ...

# LectureVerifierService
class LectureVerifierService(Protocol):
    async def verify(
        self, question: str, answer: str, sources: list[LectureSource]
    ) -> LectureVerificationResult: ...
```

### Data Flow: Index Build

```
Client
  POST /api/v4/lecture/qa/index/build
    {session_id, user_id, rebuild: false}
    │
    ▼
LectureIndexService.build_index()
  │
  ├─→ Validate session ownership
  │
  ├─→ Check if qa_index_built (skip if true and !rebuild)
  │
  ├─→ SELECT SpeechEvent WHERE session_id AND is_final=true ORDER BY start_ms
  │
  ├─→ Normalize text + tokenize (Japanese tokenizer)
  │
  ├─→ BM25Okapi.build_index(corpus) [asyncio.to_thread]
  │
  ├─→ BM25Store.put(session_id, index, chunk_map, metadata)
  │
  └─→ UPDATE LectureSession SET qa_index_built = true
    │
    ▼
Response {index_version, chunk_count, built_at}
```

### Data Flow: Ask Question

```
Client
  POST /api/v4/lecture/qa/ask
    {session_id, user_id, question, retrieval_mode}
    │
    ▼
LectureQAService.ask()
  │
  ├─→ Validate session ownership + qa_index_built
  │
  ├─→ FollowupService.resolve_query()
  │     ├─→ Load recent QATurns (feature=lecture_qa)
  │     └─→ Rewrite to standalone query using history
  │
  ├─→ RetrievalService.retrieve(standalone_query, mode)
  │     ├─→ BM25Store.get(session_id)
  │     ├─→ BM25.get_top_n(tokens, documents, top_k)
  │     └─→ if source-plus-context: expand with neighbors + dedupe
  │
  ├─→ If no sources → return fallback
  │
  ├─→ AnswererService.answer(question, sources, history)
  │     └─→ Azure OpenAI grounded generation
  │
  ├─→ VerifierService.verify(answer, sources)
  │     ├─→ Azure OpenAI citation check
  │     ├─→ If failed: constrained repair (once)
  │     └─→ If still failed: low-confidence fallback
  │
  └─→ Persist QATurn(
        feature=lecture_qa,
        citations_json=sources,
        verifier_supported=true
      )
    │
    ▼
Response {
  answer,
  confidence,
  sources: LectureSource[],
  verification_summary
}
```

### Error Handling

| Domain Exception | HTTP Status | Condition |
|------------------|-------------|-----------|
| `LectureSessionNotFoundError` | 404 | Session not found |
| `LectureSessionInactiveError` | 409 | Session not active |
| `LectureQAIndexNotBuiltError` | 409 | Index not built yet |
| `LectureQAIndexBuildInProgressError` | 409 | Index build in progress |
| `AzureOpenAITimeoutError` | 503 | Azure call timeout |

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| BM25 in-memory cache per session | Low latency for active sessions; simple scaling model |
| SpeechEvent rows as BM25 chunks | Reuses finalized subtitle data without schema churn |
| source-plus-context expansion | Improves answer quality by including surrounding context |
| Follow-up query rewrite | Improves retrieval for pronoun/ellipsis references |
| Verifier repair strategy | Single repair attempt for cost control; fallback on failure |
| Feature-based QATurn partitioning | Keeps lecture/procedure QA history unified but queryable |

### Dependencies to Add

```toml
[project]
dependencies = [
    "rank-bm25>=0.2",           # BM25 local search
    "openai>=1.0",              # Azure OpenAI client
    "sudachipy>=0.6",           # Japanese tokenizer
]
```

### Source Format with Timestamps

```python
# LectureSource for speech events
LectureSource(
    chunk_id=speech_event.id,
    type="speech",
    text=speech_event.text,
    timestamp=format_ms_to_mmss(speech_event.start_ms),  # "05:23"
    start_ms=speech_event.start_ms,
    end_ms=speech_event.end_ms,
    speaker=speech_event.speaker,
    bm25_score=score,
)

# Format for Azure OpenAI prompt
def format_source_for_llm(source: LectureSource) -> str:
    if source.type == "speech":
        return f"[SPEECH: {source.timestamp}] {source.text}"
    else:  # visual
        return f"[VISUAL] {source.text}"
```

### Confidence Scoring Formula

```python
def calculate_confidence(
    bm25_scores: list[float],
    source_count: int,
    verification_passed: bool,
) -> Literal["high", "medium", "low"]:
    # Normalize BM25 score (0-1)
    max_score = max(bm25_scores) if bm25_scores else 0
    normalized_bm25 = min(max_score / 10.0, 1.0)

    # Source count factor (0-1, capped at 5)
    source_factor = min(source_count / 5.0, 1.0)

    # Verification score (0 or 1)
    verification_score = 1.0 if verification_passed else 0.0

    # Weighted combination
    confidence = (
        0.4 * normalized_bm25 +
        0.3 * source_factor +
        0.3 * verification_score
    )

    if confidence > 0.7:
        return "high"
    elif confidence > 0.4:
        return "medium"
    return "low"
```

### Verifier Prompt Pattern (Claim-by-Claim)

```python
VERIFIER_PROMPT = """
Given an answer and source documents, verify each factual claim.

Answer: {answer}

Sources:
{sources_formatted}

Task: For each claim in the answer:
1. Extract the claim
2. Check if it's supported by sources
3. Mark: SUPPORTED | PARTIAL | NOT_SUPPORTED
4. If NOT_SUPPORTED, provide correction

Return JSON format with verification summary.
"""
```

### Multi-Field Score Fusion (Future Enhancement)

For speech + visual content (future OCR integration):

```python
class LectureRetrievalService:
    async def retrieve_with_fusion(
        self,
        session_id: str,
        query: str,
        speech_weight: float = 0.7,
        visual_weight: float = 0.3,
    ) -> list[LectureSource]:
        speech_scores = self._bm25_speech.get_scores(query)
        visual_scores = self._bm25_visual.get_scores(query)

        # Weighted fusion
        combined = (
            speech_weight * speech_scores +
            visual_weight * visual_scores
        )

        top_indices = np.argsort(combined)[::-1][:top_k]
        return [self._all_sources[i] for i in top_indices]
```

### Thread-Safe BM25 Pattern (CRITICAL)

**⚠️ rank-bm25 is NOT thread-safe**

Must create new BM25Okapi instance per request:

```python
class LectureBM25Index:
    """Thread-safe BM25 index with cached tokenization."""

    def __init__(self):
        self._chunks: list[dict] = []
        self._tokenized_corpus: list[list[str]] = []  # Cache tokenization
        self._tokenizer = dictionary.Dictionary().create()
        self._mode = tokenizer.Tokenizer.SplitMode.C  # Preserve compounds

    def add_speech_events(self, events: list[SpeechEvent]):
        """Add events and update tokenized corpus."""
        for event in events:
            self._chunks.append({
                "id": event.id,
                "text": event.text,
                "start_ms": event.start_ms,
                "type": "speech",
            })
            # Tokenize once, store for reuse
            tokens = [m.surface() for m in self._tokenizer.tokenize(event.text, self._mode)]
            self._tokenized_corpus.append(tokens)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        mode: Literal["source-only", "source-plus-context"] = "source-only",
        context_window: int = 1,
    ) -> list[dict]:
        """Thread-safe retrieval with context expansion."""
        # Create BM25 instance per request (safe for concurrent use)
        bm25 = BM25Okapi(self._tokenized_corpus, k1=1.2, b=0.5)

        # Tokenize query
        query_tokens = [m.surface() for m in self._tokenizer.tokenize(query, self._mode)]

        # Get top-k indices
        top_indices = bm25.get_top_n(query_tokens, list(range(len(self._chunks))), n=top_k)

        # Expand context if requested
        if mode == "source-plus-context" and context_window > 0:
            expanded_indices = set()
            for idx in top_indices:
                for offset in range(-context_window, context_window + 1):
                    neighbor_idx = idx + offset
                    if 0 <= neighbor_idx < len(self._chunks):
                        expanded_indices.add(neighbor_idx)
            top_indices = sorted(expanded_indices)

        return [self._chunks[i] for i in top_indices]
```

### SudachiPy Configuration

```python
# Module-level singleton (FastAPI startup)
_tokenizer: tokenizer.Tokenizer | None = None

def get_tokenizer() -> tokenizer.Tokenizer:
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = dictionary.Dictionary().create()
    return _tokenizer

# Mode C for lecture content (preserves compound terms)
MODE_C = tokenizer.Tokenizer.SplitMode.C
```

### Context Expansion Pattern

```python
def retrieve_with_context(
    chunks: list[dict],
    top_indices: list[int],
    context_window: int = 1,
) -> list[dict]:
    """Post-retrieval expansion with deduplication."""
    expanded_indices = set()
    for idx in top_indices:
        for offset in range(-context_window, context_window + 1):
            neighbor_idx = idx + offset
            if 0 <= neighbor_idx < len(chunks):
                expanded_indices.add(neighbor_idx)
    return [chunks[i] for i in sorted(expanded_indices)]
```

### BM25 Parameters for Japanese

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `k1` | 1.2-1.5 | Japanese text has shorter terms, lower saturation |
| `b` | 0.5-0.75 | Lecture chunks are similar length, less normalization |
| `top_k` | 5-10 | Balance context vs. noise |
| `context_window` | 0-2 | 0 for source-only, 1-2 for expanded context |
| Sudachi mode | C | Preserve compound terms (e.g., "国家公務員") |

### Implementation Task Breakdown

| ID | Task | Dependencies |
|----|------|--------------|
| 1 | Add dependencies (rank-bm25, openai, sudachipy) | None |
| 2 | Create schemas/lecture_qa.py | 1 |
| 3 | Create lecture_bm25_store.py (cache + lock) | 1 |
| 4 | Create lecture_index_service.py | 2, 3 |
| 5 | Create lecture_followup_service.py | 2 |
| 6 | Create lecture_retrieval_service.py | 3 |
| 7 | Create lecture_answerer_service.py | 2 |
| 8 | Create lecture_verifier_service.py | 2 |
| 9 | Create lecture_qa_service.py (orchestrator) | 4, 5, 6, 7, 8 |
| 10 | Create api/v4/lecture_qa.py + DI wiring | 9 |
| 11 | Write unit tests | Parallel with 4-10 |
| 12 | Write integration tests | 10 |

### Success Criteria

- `pytest` passes
- Index build creates BM25 index from SpeechEvents
- Ask returns grounded answers with sources
- Follow-up questions use conversation context
- Verifier validates citations and falls back gracefully
- `source-plus-context` mode includes neighboring chunks

## F1 OCR Event Persistence Planning (2026-02-20)

### Project: F1 Step 4 (`f1-ocr-event-persistence`)

**Goal**: Add OCR visual-event ingestion and persistence to lecture live flow (`/api/v4/lecture/visual/event` + `visual_events` table), while preserving existing ownership checks and fallback-safe behavior.

### Scope

- **Include**
  - Multipart visual event ingest endpoint (`session_id`, `timestamp_ms`, `source`, `change_score`, `image`)
  - OCR result persistence with `quality` classification (`good|warn|bad`)
  - Session ownership and active-status enforcement
  - Schema/service/API test coverage for success + failure paths
- **Exclude**
  - 30-second summary generation
  - session finalize workflow
  - lecture index build/search extension
  - frontend camera capture implementation

### Planned Architecture

- Extend existing lecture vertical slice:
  - `app/api/v4/lecture.py` (thin route + DI)
  - `app/services/lecture_live_service.py` (business policy + persistence)
  - `app/models/visual_event.py` (new ORM model)
  - `app/schemas/lecture.py` (visual ingest response contract)
- Introduce OCR adapter boundary:
  - `app/services/vision_ocr_service.py` (protocol + swappable implementation)
  - keep tests deterministic with non-networked fake/stub path

### Key Decisions

1. **Persist-first fallback policy**
   - OCR failure should not hard-fail the lecture flow.
   - Persist event with degraded quality (`quality=bad`) and safe defaults.

2. **Privacy-safe default**
   - Do not persist raw image bytes in DB.
   - Keep `blob_path` nullable for later storage integration.

3. **Error semantics aligned with existing lecture APIs**
   - Unknown/other-user session: `404`
   - Non-active session: `409`
   - Request validation failure: existing `400 validation_error` contract

4. **Scope freeze to F1 step-4**
   - No summary/finalize/index side expansion in this feature.

## F1 OCR Event Persistence Implementation (2026-02-20)

### Implemented Scope

- Added `POST /api/v4/lecture/visual/event` multipart endpoint under lecture router.
- Added `visual_events` persistence model and `LectureSession` relationship.
- Extended lecture live service with OCR visual ingest orchestration.
- Added OCR adapter boundary (`VisionOCRService`) with deterministic default implementation (`NoopVisionOCRService`).
- Enforced ownership/active-session guards consistent with existing lecture endpoints.
- Enforced JPEG-only upload validation at schema validation layer for MVP.
- Added fallback-safe behavior: OCR provider errors still persist event with `quality=bad`.

### Delivered Files

- `app/models/visual_event.py`
- `app/services/vision_ocr_service.py`
- `app/api/v4/lecture.py`
- `app/services/lecture_live_service.py`
- `app/schemas/lecture.py`
- `tests/api/v4/test_lecture.py`
- `tests/unit/services/test_lecture_live_service.py`
- `tests/unit/schemas/test_lecture_schemas.py`
- wiring updates:
  - `app/models/lecture_session.py`
  - `app/models/__init__.py`
  - `app/main.py`
  - `tests/conftest.py`
  - `app/services/__init__.py`
  - `app/schemas/__init__.py`
  - `pyproject.toml` (`python-multipart` added)

### Verification Results

- Changed-scope checks:
  - `uv run ruff check <changed files>`: pass
  - `uv run ruff format --check <changed files>`: pass
  - `uv run ty check app/`: pass
  - `uv run pytest tests/unit/schemas/test_lecture_schemas.py tests/unit/services/test_lecture_live_service.py tests/api/v4/test_lecture.py -q`: pass (38 passed)
- Full-suite checks:
  - `uv run pytest -v`: pass (122 passed, 1 skipped)
  - `uv run ruff check .`: fails on pre-existing unrelated files under `.claude/hooks`, `.claude/skills`, and `tests/unit/services/test_lecture_qa_service.py`
  - `uv run ruff format --check .`: fails on pre-existing unrelated files under `.claude/hooks` and others

### Post-Review Hardening (High/Medium Findings Fixed)

- Added bounded-read upload guard for visual ingest to prevent unbounded memory growth:
  - configurable max via `lecture_visual_max_image_bytes`
  - read limit enforced before validation
- Added JPEG signature verification in addition to MIME header checks.
- Added OCR failure observability:
  - introduced `VisionOCRServiceError`
  - fallback path now records warning logs with error type before degrading to `quality=bad`
- Added authorization regression coverage for visual path:
  - cross-user session ownership rejection tests at service and API layers
- Added upload-hardening regression coverage:
  - invalid JPEG signature rejection test
  - oversized upload rejection test

## TODO

- [ ] Test Agent Teams workflow end-to-end with a real project
- [ ] Update hooks for Agent Teams quality gates
- [ ] Evaluate optimal team size for /team-implement
- [ ] Implement Sprint0 backend following this design
- [ ] Validate AsyncClient approach with actual pytest run
- [ ] Implement lecture QA index build endpoint (`/api/v4/lecture/qa/index/build`) and BM25 in-memory store
- [ ] Implement lecture QA ask endpoint with follow-up rewrite, retrieval modes, Azure answerer, and verifier pipeline
- [ ] Add lecture QA unit/integration tests for verifier-fail fallback, no-source fallback, and context-expansion behavior
- [x] Implement Sprint4 step-4 `f1-ocr-event-persistence` from approved startproject plan
- [x] Implement Sprint3 `sprint3-f1-speech-events-and-subtitles` from approved startproject plan
- [x] Implement Sprint2 procedure-qa-minimal from approved startproject plan

## Open Questions

- [ ] Optimal team size for /team-implement (2-3 vs 4-5 teammates)?
- [ ] Should /team-review be mandatory or optional?
- [ ] How to handle Compaction in long Agent Teams sessions?

## Changelog

| Date | Changes |
|------|---------|
| 2026-02-20 | Applied team-review hardening for `f1-ocr-event-persistence` (High/Medium): bounded upload read/size limits, JPEG signature validation, OCR failure observability (`VisionOCRServiceError` + warning logs), and cross-user + oversized/invalid-signature regression tests |
| 2026-02-20 | Implemented Sprint4 `f1-ocr-event-persistence`: added `/api/v4/lecture/visual/event`, `visual_events` model, OCR adapter boundary, fallback-safe persistence (`quality=bad` on OCR failure), and schema/service/API tests |
| 2026-02-20 | Added Sprint4 `/startproject` plan for `f1-ocr-event-persistence`: visual OCR ingest endpoint, `visual_events` persistence, OCR adapter boundary, and fallback-safe quality policy (`quality=bad` on OCR failure) |
| 2026-02-20 | Added three Codex-native skills from checkpoint pattern mining: `planning-research-merge-gate`, `owner-lane-team-implement`, and `grounded-qa-service-playbook`; enabled all in `.codex/config.toml` |
| 2026-02-20 | Wired lecture QA Azure dependencies to runtime settings: added `AZURE_OPENAI_*` and `LECTURE_QA_RETRIEVAL_LIMIT` config fields, switched `lecture_qa` DI to use settings-backed credentials/model, and extended settings loading to include `.env.azure.generated` with `extra=ignore` |
| 2026-02-20 | Hardened Critical/High findings: added `.env.azure.generated.example` template and `.gitignore` protection for `.env.azure.generated`/env artifacts, switched lecture QA retrieval dependency to a shared in-process BM25 store, and enforced authenticated per-user `/api/v4/settings/me` access (`X-Lecture-Token` + `X-User-Id`) |
| 2026-02-20 | Added Lecture QA architecture design: BM25 index build from `SpeechEvent`, `source-only`/`source-plus-context` retrieval modes, Azure OpenAI answer+verification pipeline, and follow-up context strategy |
| 2026-02-20 | Recorded Azure MVP provisioning: created RG + Key Vault/Storage/Search/Speech/Vision/OpenAI/App Insights in `japaneast`, stored service secrets in Key Vault, and generated local bootstrap file `.env.azure.generated` |
| 2026-02-20 | Hardened Sprint3 High/Medium findings: added lecture auth/user-context guards, ownership-aware ingestion query, ROI geometry validation, and new `401`/`409`/cross-user regression tests |
| 2026-02-20 | Implemented Sprint3 `sprint3-f1-speech-events-and-subtitles`: added lecture session start/speech chunk APIs, `lecture_sessions` + `speech_events` persistence, lecture live service, and full schema/service/API tests |
| 2026-02-20 | Added Sprint3 `/startproject` plan for `sprint3-f1-speech-events-and-subtitles`: session start + finalized speech chunk persistence, backend subtitle acknowledgement contract, and strict step-3 scope boundaries |
| 2026-02-20 | Implemented Sprint1 settings-api-and-db foundation: `/api/v4/settings/me` GET/POST, SQLite async session wiring, `users` + `user_settings` models, and common 400 validation error response |
| 2026-02-20 | Rewrote Codex skills to be Claude-independent: native workflows for `/startproject`, `/team-implement`, `/team-review`, `/checkpointing`, and alias `/checkpoining` |
| 2026-02-20 | Added Codex skill bridges for `/checkpointing` and `/checkpoining` (alias) via `.codex/skills/checkpointing` and `.codex/skills/checkpoining` |
| 2026-02-20 | Added Codex skill bridges for `/startproject`, `/team-implement`, `/team-review` via `.codex/skills/*` and project skill registration in `.codex/config.toml` |
| 2026-02-20 | Prioritized next feature implementation as F2 Procedure QA after confirming current backend health + settings foundation status (`15/15` tests passing) |
| 2026-02-20 | Added Sprint2 `/startproject` plan for `procedure-qa-minimal`: fake retriever/answerer interfaces, rootless-answer fallback guard, and `qa_turns` persistence-first architecture |
| 2026-02-20 | Implemented Sprint2 `procedure-qa-minimal`: `/api/v4/procedure/ask`, fake retriever/answerer interfaces, deterministic no-source fallback policy, and `qa_turns` persistence with passing tests |
| 2026-02-20 | Fixed Sprint2 medium review findings: added procedure auth guard, moved procedure knobs to settings, switched to DI-based service wiring, and expanded validation/persistence tests |
| 2026-02-21 | Updated Sprint1 design with Researcher validation: `flag_modified()` requirement for JSON mutations, aiosqlite>=0.21.0, auto-commit session pattern |
| 2026-02-20 | Added Sprint1 Settings API & SQLite Persistence: detailed architecture, data model, service layer, API contract, TDD implementation plan |
| 2026-02-20 | Added Settings API design: SQLite JSON settings model, SQLAlchemy 2.0 async session pattern, service-layer boundary for `/api/v4/settings/me` |
| 2026-02-21 | Added Sprint0 backend architecture: FastAPI + AsyncClient + layered design |
| 2026-02-19 | Context-aware redesign: Claude=200K, Gemini=1M (codebase+research+multimodal), all subagents/teams→Opus |
| 2026-02-17 | Role clarification: Gemini → multimodal only, Codex → planning + complex code, Subagents → external research |
| 2026-02-08 | Major redesign for Opus 4.6: 1M context, Agent Teams, skill pipeline |
| | Initial |
