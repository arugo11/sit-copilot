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

### 運用ルール（このリポジトリ）

- バックエンド/フロントエンドに修正を加えた後は、**必ずサーバを再起動**してから動作確認する。
- 特に SQLite 利用時は、古いワーカープロセスが `database is locked` を誘発するため、
  検証前に既存サーバープロセスを停止してクリーン起動する。
- デモ前確認は「開始 → 終了」を1回実行して正常応答を確認する。

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

## Current Project: Sprint1 Settings API & Database

### Context
- **Goal**: SQLite永続化とユーザー設定API（GET/POST /api/v4/settings/me）を実装し、以後の全機能の土台を作る
- **Python Version**: 3.11
- **Structure**: モジュラー構造 + DB層（app/models/, app/db/, app/services/）
- **TDD**: すべてTDDで実行

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

---

## Current Project: WandB Weave Integration (2026-02-23)

### Context
- **Goal**: Integrate WandB Weave for LLM and session observability
- **Mode**: Demo (all data capture enabled including images)
- **Key files**:
  - `app/services/observability/` - Observer infrastructure
  - `app/services/observability/weave_observer_service.py` - Protocol + implementations
  - `app/services/observability/weave_dispatcher.py` - Non-blocking dispatcher
  - `app/services/observability/weave_context.py` - Session context manager
  - `app/main.py` - Weave initialization in lifespan

### Architecture
- Protocol-based `WeaveObserverService` with Noop and WandB implementations
- Async dispatcher with fire-and-forget pattern (queue + workers)
- Multimodal support: `weave.Image.from_bytes()` for slides/OCR
- Audio tracked as metadata only (Azure Blob URLs)

### Trace Structure
```
lecture.session:{session_id}
  ├─ qa.ask/followup
  │   ├─ retrieval.search (BM25 or Azure AI Search)
  │   └─ llm.answer.generate (Azure OpenAI)
  ├─ ocr.extract_text (with image preview via weave.Image)
  ├─ live.slide_change (with slide thumbnail)
  └─ live.speech_chunk (audio metadata, not raw audio)
```

### Configuration (Environment Variables)
```bash
# Enable/disable Weave
WEAVE_ENABLED=true                    # Default: true (demo mode)
WEAVE_MODE=local                      # local | cloud
WEAVE_PROJECT=sit-copilot-demo        # Project name in Weave

# Data capture (demo: all enabled)
WEAVE_CAPTURE_PROMPTS=true            # Capture LLM prompts
WEAVE_CAPTURE_RESPONSES=true          # Capture LLM responses
WEAVE_CAPTURE_IMAGES=true             # Embed images in traces
WEAVE_MAX_IMAGE_SIZE_BYTES=10485760   # 10MB limit per image

# Performance tuning
WEAVE_QUEUE_MAXSIZE=1000              # Observation queue size
WEAVE_WORKER_COUNT=2                  # Background worker count
WEAVE_TIMEOUT_MS=5000                 # Operation timeout
WEAVE_SAMPLE_RATE=1.0                 # Sampling rate (0-1)
```

### Decisions
| Decision | Rationale |
|----------|-----------|
| Protocol-based observer | Enables testing with noop implementation; zero overhead when disabled |
| Fire-and-forget dispatcher | Observability failures never impact request latency |
| weave.Image.from_bytes() | Native Weave support for image visualization in UI |
| Audio as metadata only | Audio files too large for traces; Azure Blob provides storage |
| Queue overflow = drop | Better to lose traces than block requests or crash |

### Documentation
- `.claude/docs/weave-implementation.md` - Implementation guide and architecture
- `.claude/docs/weave-multimodal.md` - Multimodal features (images, audio)
- `.claude/docs/weave-deployment.md` - Azure deployment with Weave Cloud

### Success Criteria
- Unit tests pass: `uv run pytest tests/unit/services/test_weave_*.py -v`
- Integration tests pass: `uv run pytest tests/integration/test_weave_integration.py -v`
- Weave UI displays traces (local mode: http://localhost:8080)
- Images visible in OCR and slide transition traces
- No performance impact on request handlers

## Session History

### 2026-02-20

- 0 commits, 0 files changed
- Agent Teams: sprint0-review (4 teammates, 0/3 tasks)
- Agent Teams: sprint1-implement (4 teammates, 2/8 tasks)
- Agent Teams: auc-095-phase1-oof-ensemble (3 teammates, 0/2 tasks)
- Agent Teams: auc-0-95-improvement (3 teammates, 2/8 tasks)

## Azure Service
Azure関係で操作が必要になったばあい, Azure CLIの使い方について調べてAzure CLIで解決してください.