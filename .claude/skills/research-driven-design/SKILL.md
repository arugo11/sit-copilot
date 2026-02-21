# Research-Driven Design

外部リサーチ + ドキュメンテーション + 設計 + 実装の一連のワークフロー。

## When to Use

- 新しいライブラリ・技術を採用する時
- アーキテクチャ設計の意思決定が必要な時
- 複雑な実装の計画を立てる必要がある時
- 外部 API との統合を行う時

## Trigger Phrases

- "リサーチして"
- "ライブラリを比較して"
- "アーキテクチャを設計"
- "実装計画を立てて"
- "外部 API を調査"

## Workflow

```
Phase 1: Research (Gemini CLI)
  外部ドキュメント・API仕様・ベストプラクティスを調査
  → .claude/docs/research/{topic}.md

Phase 2: Library Constraints Doc
  ライブラリの制約・注意点をドキュメント化
  → .claude/docs/libraries/{library}.md

Phase 3: Architecture Design (Codex)
  設計決定・トレードオフ・実装計画を策定
  → .claude/docs/research/{topic}-architecture.md

Phase 4: Implementation
  設計ドキュメントに従って実装
```

## Pattern

### Phase 1: External Research (Gemini)

```bash
# Research topic: library, API, or technology
gemini -p "
Research: Azure OpenAI API integration with Python

Find:
1. Latest official documentation
2. Authentication methods (API key, Azure AD)
3. Rate limits and quotas
4. Common pitfalls and constraints
5. Best practices for production
6. Error handling patterns

Include code examples and version requirements.
" 2>/dev/null

# Save results to research doc
# → .claude/docs/research/f1-azure-openai-summary.md
```

### Phase 2: Library Constraints

```markdown
<!-- .claude/docs/libraries/azure-openai.md -->

# Azure OpenAI (openai>=1.0)

## Version
- Minimum: 1.0.0
- Recommended: 1.12.0+

## Key Constraints

### Authentication
- API key must be passed via `api_key` parameter
- For Azure: `azure_endpoint` required

### Rate Limits
- Free tier: 3 requests/minute
- Standard tier: varies by deployment

### Common Pitfalls
- **Timeout**: Default 600s, but may need adjustment for long completions
- **Streaming**: Requires async iterator handling
- **Error responses**: Check `error.code` field

## Code Pattern
```python
from openai import AsyncAzureOpenAI

client = AsyncAzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_version="2024-02-01"
)
```
```

### Phase 3: Architecture Design (Codex)

```bash
# Validate architecture and get recommendations
codex exec --model gpt-5.3-codex --sandbox read-only --full-auto "
Review architecture for F1 Azure OpenAI Summary Integration.

Requirements:
- Integrate Azure OpenAI for lecture summary generation
- Support both standard and streaming responses
- Handle rate limits and retries
- Source-only constraint (use only provided context)

Constraints:
- Python 3.11
- FastAPI async endpoints
- SQLAlchemy 2.0 for persistence
- Use openai>=1.0

Provide:
1. Architecture diagram
2. Module structure
3. Key design decisions with rationale
4. Error handling strategy
5. Testing approach
" 2>/dev/null

# Save to architecture doc
# → .claude/docs/research/f1-azure-openai-summary-architecture.md
```

### Phase 4: Implementation

```bash
# Follow architecture doc to implement
# 1. Create service modules
# 2. Add schemas
# 3. Add API endpoints
# 4. Write tests

# Verify
uv run pytest
uv run ruff check .
uv run ty check
```

## Example: F1 Azure OpenAI Summary Integration

### Research Output Structure

```
.claude/docs/research/
├── f1-azure-openai-summary.md              # Gemini research
├── f1-azure-openai-summary-architecture.md # Codex design
└── f1-azure-openai-summary-codebase.md     # Implementation notes

.claude/docs/libraries/
└── azure-openai-summary.md                 # Library constraints
```

### Architecture Doc Template

```markdown
# {Feature} Architecture

## Overview
{Brief description of the feature}

## Requirements
- {Requirement 1}
- {Requirement 2}

## Design Decisions

| Decision | Rationale | Alternatives Considered |
|----------|-----------|-------------------------|
| Use AsyncAzureOpenAI client | Matches FastAPI async flow | Sync client, HTTPX |
| Source-only constraint | Prevents hallucinations | Free-form generation |

## Module Structure

```
app/services/
├── lecture_summary_service.py      # Orchestrator
└── azure_openai_client.py          # Azure OpenAI wrapper
```

## API Design

```
POST /api/v4/lecture/{id}/summary
Request: {schema}
Response: {schema}
```

## Error Handling
- Rate limit: Exponential backoff
- Invalid key: 401 error
- Timeout: 30s with retry

## Testing Strategy
- Mock `urllib.request.urlopen`
- Test error scenarios
- Coverage target: 80%+
```

## Key Points

### 1. Gemini CLI for Research

- **1M context** で大規模なドキュメント調査
- **Google Search grounding** で最新情報取得
- マルチモーダルファイル（PDF/画像）も読み取り可能

```bash
# Research with file input
gemini -p "Analyze this architecture diagram" < diagram.png 2>/dev/null
```

### 2. Codex for Design

- **計画・設計**に特化
- トレードオフ評価
- 実装計画のステップ分解

### 3. Documentation Persistence

- すべての調査結果を `.claude/docs/` に保存
- 後で参照可能
- チームメンバーと共有

### 4. Library Constraints Docs

- ライブラリごとに制約をドキュメント化
- `.claude/docs/libraries/{name}.md`
- バージョン、制約、パターンを記録

## Decision Documentation Pattern

```markdown
## Decision: {Title}

**Status:** Accepted | Proposed | Deprecated | Superseded

**Context:**
{Background and problem statement}

**Decision:**
{What we decided}

**Consequences:**
- Positive: {benefits}
- Negative: {drawbacks}
- Risk: {potential risks}

**Alternatives Considered:**
1. {Option A} - {why rejected}
2. {Option B} - {why rejected}
```

## Commands Reference

```bash
# Research (Gemini)
gemini -p "Research: {topic}" 2>/dev/null

# Architecture Design (Codex)
codex exec --model gpt-5.3-codex --sandbox read-only "{question}"

# View research docs
ls .claude/docs/research/

# View library constraints
ls .claude/docs/libraries/
```

## Checklist

- [ ] 外部リサーチ完了（Gemini）
- [ ] ライブラリ制約をドキュメント化
- [ ] 設計レビュー完了（Codex）
- [ ] アーキテクチャドキュメント作成
- [ ] 実装計画ステップ化
- [ ] 実装開始前に設計承認
