# Claude Code Orchestra

**マルチエージェント協調フレームワーク（Opus 4.6 + Agent Teams 対応）**

Claude Code が全体統括し、Codex CLI（計画・難実装）と Gemini CLI（1M context 活用）を使い分ける。

---

## Agent Roles — 役割分担

| Agent | Model | Role | Use For |
|-------|-------|------|---------|
| **Claude Code（メイン）** | Opus 4.6 | 全体統括 | ユーザー対話、タスク管理、簡潔なコード編集 |
| **general-purpose（サブエージェント）** | **Opus** | 実装・Codex委譲 | コード実装、Codex委譲、ファイル操作 |
| **codex-debugger（サブエージェント）** | **Opus** | エラー解析 | Codex CLI でエラーの根本原因分析・修正提案 |
| **gemini-explore（サブエージェント）** | **Opus** | 大規模分析・調査 | コードベース理解、外部リサーチ、マルチモーダル読取（1M context） |
| **Agent Teams チームメイト** | **Opus**（デフォルト） | 並列協調 | /startproject, /team-implement, /team-review |
| **Codex CLI** | gpt-5.3-codex | 計画・難しい実装 | アーキテクチャ設計、実装計画、複雑なコード実装 |
| **Gemini CLI** | gemini-3-pro | 1M context エージェント | コードベース分析、リサーチ、マルチモーダル読取 |

### 判断フロー

```
タスク受信
  ├── マルチモーダルファイル（PDF/動画/音声/画像）がある？
  │     → YES: Gemini にファイルを渡して内容抽出
  │
  ├── コードベース全体の理解・大規模分析が必要？
  │     → YES: Gemini に委譲（1M context 活用）
  │
  ├── 外部情報・リサーチ・サーベイが必要？
  │     → YES: Gemini に委譲（Google Search grounding 活用）
  │
  ├── 計画・設計・難しいコードが必要？
  │     → YES: Codex に相談 or 実装させる
  │
  └── 通常のコード実装？
        → メインが直接 or サブエージェントに委託
```

---

## Quick Reference

### Codex を使う時

- **計画・設計**（「どう実装？」「アーキテクチャ」「計画を立てて」）
- **難しいコード実装**（複雑なアルゴリズム、最適化、マルチステップ実装）
- **デバッグ**（「なぜ動かない？」「エラーの原因は？」）
- **比較検討**（「AとBどちらがいい？」「トレードオフは？」）

→ 詳細: `.claude/rules/codex-delegation.md`

### Gemini を使う時

Gemini CLI は **1M トークンのコンテキスト**を持ち、以下の3つの役割を担う:

- **マルチモーダルファイル読取（必須・自動委譲）**
  - PDF、動画、音声、画像ファイルが登場したら自動で Gemini に渡す
  ```bash
  gemini -p "{抽出したい情報}" < /path/to/file 2>/dev/null
  ```
- **コードベース・リポジトリ理解**
  - プロジェクト全体の構造分析、パターン把握、依存関係の理解
  - メインの 200K コンテキストでは収まらない大規模分析を委譲
  ```bash
  gemini -p "Analyze this codebase: structure, key modules, patterns, dependencies" 2>/dev/null
  ```
- **外部リサーチ・サーベイ**
  - 最新ドキュメント調査、ライブラリ比較、ベストプラクティス調査
  - Gemini の Google Search grounding を活用
  ```bash
  gemini -p "Research: {topic}. Find latest best practices, constraints, and recommendations" 2>/dev/null
  ```

> スクリーンショットの単純確認は Claude の Read ツールで直接可能。

→ 詳細: `.claude/rules/gemini-delegation.md`

### サブエージェントを使う時

- **コード実装**（メインのコンテキストを節約したい場合）
- **Codex 委譲**（計画・設計の相談をサブエージェント経由で）
- **調査結果の整理** → `.claude/docs/research/` に保存

---

## Context Management

Claude Code (Opus 4.6) のコンテキストは **200K トークン**（実質 **140-150K**、ツール定義等で縮小）。
> ※ API pay-as-you-go (Tier 4+) では 1M Beta が利用可能。

**Compaction 機能**により、長時間セッションでもサーバーサイドで自動要約される。

**Gemini CLI は 1M トークン**のコンテキストを持つため、大規模分析・調査は Gemini に委譲する。

### モデル選択方針

| エージェント | モデル | 理由 |
|------------|--------|------|
| general-purpose | **Opus** | 高い推論能力でコード実装・Codex委譲を高品質に実行 |
| codex-debugger | **Opus** | エラー解析には高い推論能力が必要。Codex への的確な質問生成に強い |
| gemini-explore | **Opus** | Gemini CLI（1M context）を活用した大規模分析・調査・マルチモーダル処理の統括 |
| Agent Teams | **Opus**（デフォルト） | `CLAUDE_CODE_SUBAGENT_MODEL` で設定。高い推論能力で並列作業に対応 |

### 呼び出し基準

| 出力サイズ | 方法 | 理由 |
|-----------|------|------|
| 短い（〜20行） | 直接呼び出しOK | 200Kコンテキストで吸収可能 |
| 中程度（20-50行） | サブエージェント経由を推奨 | コンテキスト効率化 |
| 大きい（50行以上） | サブエージェント → ファイル保存 | 詳細は `.claude/docs/` に永続化 |
| コードベース全体分析 | **Gemini 経由** | 1M context を活用 |
| 外部リサーチ | **Gemini 経由** | Google Search grounding 活用 |

### 並列処理の選択

| 目的 | 方法 | 適用場面 |
|------|------|----------|
| 結果を取得するだけ | サブエージェント | Codex相談、調査、実装 |
| 相互通信が必要 | **Agent Teams** | 並列実装、並列レビュー |

---

## Workflow

```
/startproject <機能名>     Phase 1-3: 理解 → 調査&設計 → 計画
    ↓ 承認後
/team-implement            Phase 4: Agent Teams で並列実装
    ↓ 完了後
/team-review               Phase 5: Agent Teams で並列レビュー
```

1. Gemini でコードベースを分析（1M context）+ Claude がユーザーと要件ヒアリング
2. Gemini で外部調査 + Codex で設計・計画（並列可）
3. Claude が調査と設計を統合し、計画をユーザーに提示
4. 承認後、`/team-implement` で並列実装
5. `/team-review` で並列レビュー

→ 詳細: `/startproject`, `/team-implement`, `/team-review` skills

---

## Tech Stack

- **Python** / **uv** (pip禁止)
- **ruff** (lint/format) / **ty** (type check) / **pytest**
- `poe lint` / `poe test` / `poe all`

→ 詳細: `.claude/rules/dev-environment.md`

---

## Documentation

| Location | Content |
|----------|---------|
| `.claude/rules/` | コーディング・セキュリティ・言語ルール |
| `.claude/docs/DESIGN.md` | 設計決定の記録 |
| `.claude/docs/research/` | 調査結果（サブエージェント / レビュー） |
| `.claude/docs/libraries/` | ライブラリ制約ドキュメント |
| `.claude/logs/cli-tools.jsonl` | Codex/Gemini入出力ログ |

---

## Language Protocol

- **思考・コード**: 英語
- **ユーザー対話**: 日本語

---

## Current Project: F4 Lecture QA (講義後QA)

### Context
- **Goal**: 講義後に実際の講義発言・板書・スライドを根拠として質問に答えるF4機能を実装する
- **Python Version**: 3.11
- **Approach**: F4.1 ローカル検索（BM25）のみ、source-only + source-plus-context モード、完全版 LLM検証

### Key Files
```
app/
├── api/v4/
│   └── lecture_qa.py        # NEW: /qa/index/build, /qa/ask, /qa/followup
├── schemas/
│   └── lecture_qa.py        # NEW: QA request/response schemas
├── services/
│   ├── lecture_qa_service.py         # NEW: Orchestrator (retrieve->answer->verify)
│   ├── lecture_retrieval_service.py  # NEW: BM25-based retrieval
│   ├── lecture_index_service.py      # NEW: Index builder from SpeechEvents
│   ├── lecture_answerer_service.py   # NEW: Azure OpenAI answer generation
│   ├── lecture_verifier_service.py   # NEW: LLM-based citation verification
│   └── lecture_followup_service.py   # NEW: Follow-up context handling
tests/
├── api/v4/
│   └── test_lecture_qa.py   # NEW: QA API tests
└── unit/
    ├── schemas/
    │   └── test_lecture_qa_schemas.py   # NEW: Schema tests
    └── services/
        └── test_lecture_qa_service.py   # NEW: Service tests
```

### Dependencies
```toml
[project]
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0",
    "aiosqlite>=0.21.0",
    "rank-bm25>=0.2.2",        # NEW: Local BM25 search
    "openai>=1.0",             # NEW: Azure OpenAI integration
]
```

### Architecture
```
POST /api/v4/lecture/qa/index/build
  -> LectureIndexService.build_index()
     -> Fetch SpeechEvents (is_final=True) from DB
     -> Build BM25 index (tokenized corpus)

POST /api/v4/lecture/qa/ask
  -> LectureQAService.ask()
     -> LectureFollowupService.rewrite_question()  # Resolve pronouns/context
     -> LectureRetrievalService.retrieve()         # BM25 search
     -> LectureAnswererService.generate_answer()   # Azure OpenAI
     -> LectureVerifierService.verify()            # LLM-based verification
     -> Persist QATurn (feature=lecture_qa)
```

### Library Constraints
**rank-bm25**:
- No incremental updates → rebuild entire index when new chunks added
- No built-in tokenization → implement preprocessing (lowercase, split)
- Use `k1=1.2-1.5, b=0.5-0.75` for Japanese shorter documents
- CPU-bound → use `asyncio.to_thread()` for BM25 operations

**Azure OpenAI**:
- **API Version**: `2024-02-15-preview` (required for Cognitive Services endpoints)
- **Endpoint Format**: `https://japaneast.api.cognitive.microsoft.com` (region-based)
- **Deployment Name**: Must match deployed model name (e.g., `gpt-4.1`)
- Source-only constraint: "Use ONLY information from the sources"
- Citation format: `{"type": "speech|visual", "timestamp": "...", "text": "..."}`
- Verifier pattern: claim-by-claim validation with fallback
- Error handling: `LectureAnswererError` → local grounded response (graceful degradation)

**SpeechEvent as Chunk**:
- Primary source unit = one `SpeechEvent` row (`chunk_id = speech_event.id`)
- Preserves timestamp precision for citations
- Filter by `is_final=True` only

### Decisions
| Decision | Rationale |
|----------|-----------|
| BM25 index in process-local cache | Low latency for active sessions; no persistence needed |
| SpeechEvent rows as chunk units | Reuses existing data; preserves timestamp precision |
| source-only + source-plus-context modes | Matches SPEC §5.3.2; supports future expansion |
| LLM-based Verifier | Ensures citation-grounded answers; SPEC §11.5 requirement |
| Follow-up rewrite before retrieval | Improves recall for pronoun/ellipsis queries |

### Success Criteria
- `uv run pytest -q` passes (green)
- POST /api/v4/lecture/qa/index/build builds BM25 index from SpeechEvents
- POST /api/v4/lecture/qa/ask returns answer with citations
- No sources → deterministic fallback
- Verifier fails → repair or fallback
- Follow-up questions resolve context correctly
- `uv run ruff check .` passes
- `uv run ty check app/` passes

---

## Previous Project: Sprint1 Settings API & Database (Completed)

Sprint1 successfully implemented SQLite persistence and user settings API.

### Key Files
```
app/
├── main.py                  # FastAPI instance & root router
├── api/v4/
│   ├── health.py            # (existing) Health endpoint
│   └── settings.py          # NEW: Settings API routes
├── core/
│   └── config.py            # (existing, add database_url)
├── db/
│   ├── base.py              # NEW: SQLAlchemy Base
│   └── session.py           # NEW: Async session dependency
├── models/
│   └── user_settings.py     # NEW: UserSettings ORM model
├── services/
│   └── settings_service.py  # NEW: Settings business logic
└── schemas/
    ├── health.py            # (existing)
    └── settings.py          # NEW: Settings request/response models
tests/
├── conftest.py              # (existing, add db fixture)
├── api/v4/
│   ├── test_health.py       # (existing)
│   └── test_settings.py     # NEW: Settings API tests
└── unit/
    ├── schemas/
    │   └── test_settings_schemas.py   # NEW: Schema validation tests
    └── services/
        └── test_settings_service.py   # NEW: Service layer tests
```

### Dependencies
```toml
[project]
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0",    # NEW: ORM with async support
    "aiosqlite>=0.21.0",           # NEW: Async SQLite driver
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "pytest-mock>=3.12",
    "pytest-asyncio>=0.25.1",
    "httpx>=0.26",
    "ruff>=0.8",
    "ty>=0.11",
]
```

### Architecture
```
┌─────────────────────────────────┐
│   API Layer (routes)            │  ← HTTP endpoints only (thin)
├─────────────────────────────────┤
│   Service Layer (business)      │  ← Business logic, flag_modified()
├─────────────────────────────────┤
│   Model Layer (database)        │  ← ORM definitions (UserSettings)
├─────────────────────────────────┤
│   DB Layer (session)            │  ← AsyncSession, engine
└─────────────────────────────────┘
```

### Library Constraints
**SQLAlchemy 2.0 + aiosqlite**:
- Use `Mapped[]` type hints for modern models
- `expire_on_commit=False` in session factory (prevents lazy loading errors)
- Always `await` for DB operations: `await db.execute()`, `await db.commit()`
- Auto-commit pattern: `yield session; await session.commit()` on success

**JSON Column with MutableDict**:
- Always use `flag_modified()` after mutating JSON fields
- Use `default=lambda: {}` to avoid shared mutable defaults
- Write helper in service layer to avoid forgetting flag_modified

**Pydantic v2**:
- Use `ConfigDict(from_attributes=True)` (changed from v1's `orm_mode`)
- Use `model_validate()` instead of `parse_obj()` for ORM conversion

**Testing**:
- In-memory SQLite: `sqlite+aiosqlite:///:memory:`
- Use `begin_nested()` SAVEPOINT pattern for automatic rollback per test
- `asyncio_mode = "auto"` in pyproject.toml (required)

### Decisions
| Decision | Rationale |
|----------|-----------|
| SQLite JSON settings model | Flexible, schema-less user preferences; SQLite JSON functions remain available |
| SQLAlchemy 2.0 async stack | Matches FastAPI async flow; consistent ORM access pattern |
| Auto-commit session pattern | Simpler route handlers; consistent transaction handling |
| flag_modified() for JSON | Reliable mutation detection; avoids lost changes |
| Settings API boundary: API → Service | Keeps HTTP details out of business logic; enables isolated unit tests |

### Success Criteria
- `uv run pytest -q` passes (green)
- GET /api/v4/settings/me returns 200 with JSON
- POST /api/v4/settings/me creates/updates settings
- Validation errors return 400
- Response JSON structure matches specification
- `uv run ruff check .` passes
- `uv run ty check app/` passes

---

## Previous Project: Sprint0 Backend Scaffold (Completed)

Sprint0 successfully implemented FastAPI backend foundation with `/api/v4/health` endpoint returning 200.

## Session History

### 2026-02-20

- 0 commits, 0 files changed
- Agent Teams: sprint0-review (4 teammates, 0/3 tasks)
- Agent Teams: sprint1-implement (4 teammates, 2/8 tasks)
- Agent Teams: auc-095-phase1-oof-ensemble (3 teammates, 0/2 tasks)
- Agent Teams: auc-0-95-improvement (3 teammates, 2/8 tasks)

## Azure Service
Azure関係で操作が必要になったばあい, Azure CLIの使い方について調べてAzure CLIで解決してください.

### 2026-02-20

- 0 commits, 0 files changed
- Codex: 1 consultations
- Agent Teams: sprint0-review (4 teammates, 0/3 tasks)
- Agent Teams: sprint1-implement (4 teammates, 2/8 tasks)
- Agent Teams: auc-095-phase1-oof-ensemble (3 teammates, 0/2 tasks)
- Agent Teams: auc-0-95-improvement (3 teammates, 2/8 tasks)
- Agent Teams: f4-lecture-qa-implement (6 teammates, 3/7 tasks)

### 2026-02-20

- 0 commits, 0 files changed
- Codex: 1 consultations
- Agent Teams: sprint0-review (4 teammates, 0/3 tasks)
- Agent Teams: sprint1-implement (4 teammates, 2/8 tasks)
- Agent Teams: auc-095-phase1-oof-ensemble (3 teammates, 0/2 tasks)
- Agent Teams: auc-0-95-improvement (3 teammates, 2/8 tasks)
- Agent Teams: f4-lecture-qa-implement (6 teammates, 3/7 tasks)

### 2026-02-20

- 2 commits, 0 files changed
- Codex: 1 consultations
- Agent Teams: sprint0-review (4 teammates, 0/3 tasks)
- Agent Teams: sprint1-implement (4 teammates, 2/8 tasks)
- Agent Teams: auc-095-phase1-oof-ensemble (3 teammates, 0/2 tasks)
- Agent Teams: auc-0-95-improvement (3 teammates, 2/8 tasks)
- Agent Teams: f4-lecture-qa-implement (6 teammates, 3/7 tasks)

### 2026-02-20

- 5 commits, 0 files changed
- Codex: 1 consultations
- Agent Teams: sprint0-review (4 teammates, 0/3 tasks)
- Agent Teams: sprint1-implement (4 teammates, 2/8 tasks)
- Agent Teams: auc-095-phase1-oof-ensemble (3 teammates, 0/2 tasks)
- Agent Teams: auc-0-95-improvement (3 teammates, 2/8 tasks)
- Agent Teams: f4-lecture-qa-implement (6 teammates, 3/7 tasks)

### 2026-02-21

- 8 commits, 0 files changed
- Codex: 1 consultations
- Agent Teams: sprint0-review (4 teammates, 0/3 tasks)
- Agent Teams: sprint1-implement (4 teammates, 2/8 tasks)
- Agent Teams: auc-095-phase1-oof-ensemble (3 teammates, 0/2 tasks)
- Agent Teams: auc-0-95-improvement (3 teammates, 2/8 tasks)
- Agent Teams: f4-lecture-qa-implement (6 teammates, 3/7 tasks)

---

## Current Project: F4 QA Test Completion

### Context
- Goal: Improve test coverage for F4 Lecture QA services from 81% → 85%+
- Target services:
  1. `app/services/lecture_bm25_store.py` (0% → 80%+)
  2. `app/services/lecture_verifier_service.py` (49% → 80%+)
  3. `app/services/lecture_followup_service.py` (35% → 80%+)
- Python Version: 3.11
- Approach: Add comprehensive unit tests following existing patterns

### Key Files
```
tests/unit/services/
├── test_lecture_bm25_store.py       # NEW: BM25 store tests
├── test_lecture_verifier_service.py  # EXPAND: Azure OpenAI verification tests
└── test_lecture_followup_service.py  # NEW: Follow-up resolution tests
```

### Test Patterns (from Research)
- **rank-bm25**: NOT thread-safe, use concurrent `asyncio.gather()` tests
- **Azure OpenAI**: Patch `urllib.request.urlopen` wrapped in `asyncio.to_thread()`
- **SQLAlchemy AsyncSession**: Use `AsyncMock` or real in-memory SQLite from conftest
- **pytest-asyncio**: `asyncio_mode = "auto"` already configured

### Test Coverage Goals
| Service | Current | Target | Key Cases |
|---------|---------|--------|-----------|
| lecture_bm25_store.py | 0% | 80%+ | concurrent access, lock management |
| lecture_verifier_service.py | 49% | 80%+ | Azure OpenAI mocks, local fallback |
| lecture_followup_service.py | 35% | 80%+ | AsyncSession mocks, rewrite patterns |

### Success Criteria
- [ ] `test_lecture_bm25_store.py` created and passing
- [ ] `test_lecture_verifier_service.py` expanded to 80%+
- [ ] `test_lecture_followup_service.py` created and passing
- [ ] Overall coverage 85%+
- [ ] `uv run pytest -q` passes (green)
- [ ] `uv run ruff check .` passes
- [ ] `uv run ty check app/` passes

### Decisions
| Decision | Rationale |
|----------|-----------|
| Mock urlopen for Azure OpenAI | Services use `asyncio.to_thread(urlopen)` - mock sync function |
| Use real LectureBM25Store in tests | Pure in-memory operations, no external dependencies |
| AsyncMock for AsyncSession | Followup service loads history from DB |
| Test concurrent access with asyncio.gather | Verify thread-safety of lock management |

### 2026-02-21

- 17 commits, 100 files changed
- Codex: 2 consultations
- Agent Teams: sprint0-review (4 teammates, 0/3 tasks)
- Agent Teams: f1-azure-openai-summary-impl (0 teammates, 8/12 tasks)
- Agent Teams: sprint1-implement (4 teammates, 2/8 tasks)
- Agent Teams: auc-095-phase1-oof-ensemble (3 teammates, 0/2 tasks)
- Agent Teams: frontend-impl (5 teammates, 16/27 tasks)
- Agent Teams: auc-0-95-improvement (3 teammates, 2/8 tasks)
- Agent Teams: f4-lecture-qa-implement (6 teammates, 3/7 tasks)

### 2026-02-22

- 0 commits (uncommitted changes), 24 files changed (+1784, -137)
- Codex: 2 consultations (Azure CLI research, RAG error handling debug)
- Gemini: 1 research (codebase analysis)
- Agent Teams: rag-error-handling-fix (2 teammates, 6/6 tasks completed)
- **RAG Error Handling Fixed**: Implemented graceful degradation on Azure OpenAI failures (HTTP 200 with local fallback instead of HTTP 503)
- **Azure OpenAI Integration Completed**: Configured Cognitive Services endpoint with gpt-4.1 deployment (Japan East)
- **API Version Fix**: Discovered `2024-02-15-preview` required for Cognitive Services endpoints
- **Test Coverage**: All 345 tests passing (86% coverage)
- **Documentation Updated**: DESIGN.md + azure-openai-config-template.md + CLAUDE.md
- **Key Patterns Discovered**:
  - LLM Error Handling with Graceful Degradation (Confidence: 0.95)
  - Safe Wrapper for LLM Verification (Confidence: 0.90)
- **Azure CLI Setup**: Installed via uv tool with Python 3.10, created patched wrapper for compatibility
