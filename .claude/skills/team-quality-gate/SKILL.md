# Team Quality Gate

実装後の品質チェックを Agent Teams で実行するワークフロー。

## When to Use

- 実装が完了し、コードレビューが必要な時
- テストカバレッジを検証する必要がある時
- セキュリティ・品質・アクセシビリティを包括的にレビューする時
- マージ前の最終チェック

## Trigger Phrases

- "レビューをお願い"
- "品質チェック"
- "コードレビュー"
- "テストカバレッジを確認"
- "セキュリティレビュー"

## Workflow

```
1. /team-review を実行
   Quality Reviewer    → コーディング原則、テスト品質、設計
   Security Reviewer   → 脆弱性、シークレット、インプットバリデーション
   Test Reviewer       → カバレッジ、テストパターン、モック戦略

2. レビュー結果に基づき修正を実施

3. 再度ビルド & テスト実行

4. すべてのチェックがパスしたら完了
```

## Pattern

### Step 1: Run Team Review

```bash
# After implementation is complete
/team-review

# Or explicitly specify reviewers
/team-review --reviewers quality,security,test
```

### Step 2: Review Results

レビュアーは以下を確認し、レポートを `.claude/docs/research/` に保存:

| Reviewer | Focus | Report Location |
|----------|-------|-----------------|
| Quality Reviewer | コーディング原則、設計、可読性 | `review-quality-{feature}.md` |
| Security Reviewer | 脆弱性、シークレット、バリデーション | `review-security-{feature}.md` |
| Test Reviewer | カバレッジ、テストパターン | `review-tests-{feature}.md` |

### Step 3: Address Findings

```bash
# Read review reports
cat .claude/docs/research/review-quality-{feature}.md
cat .claude/docs/research/review-security-{feature}.md
cat .claude/docs/research/review-tests-{feature}.md

# Fix Critical and High priority issues first
# Then address Medium and Low

# Commit fixes
git add .
git commit -m "fix(review): address team-review findings

- Fix hardcoded API key (Security)
- Add error handling for edge cases (Quality)
- Improve test coverage to 85%+ (Test)"
```

### Step 4: Verify

```bash
# Run full quality gate
uv run pytest --cov
uv run ruff check .
uv run ruff format --check .
uv run ty check

# Or use poe task
poe all
```

## Review Criteria

### Quality Reviewer Checklist

- [ ] コーディング原則に従っているか
  - シンプルで読みやすいか
  - 適切な抽象化レベル
  - 早期返却（Early Return）を使用
- [ ] 型ヒントが正しいか
  - 関数すべてに型アノテーション
  - `ty check` がパス
- [ ] 設計が一貫しているか
  - 既存パターンに従っている
  - 適切な責任分離

### Security Reviewer Checklist

- [ ] シークレット管理
  - ハードコードされた API キーがない
  - 環境変数から取得している
- [ ] インプットバリデーション
  - Pydantic モデルでバリデーション
  - 外部入力を検証
- [ ] SQL インジェクション防止
  - パラメータ化クエリ使用
- [ ] エラーメッセージ
  - 過度に詳細でない
  - ログに機密情報が含まれない

### Test Reviewer Checklist

- [ ] カバレッジ
  - 80%+ 目標達成
  - 未カバーの重要パスがない
- [ ] テストパターン
  - AAA パターン使用
  - Happy path + Error cases + Edge cases
- [ ] モック戦略
  - 外部依存を適切にモック
  - モック検証（assert_called_once）

## Priority Levels

| Priority | Action | Timeline |
|----------|--------|----------|
| **Critical** | ブロッカー、即時修正必須 | マージ前 |
| **High** | 重要、早急な修正推奨 | マージ前 |
| **Medium** | 改善推奨 | 次のスプリント |
| **Low** | Nice to have | 時間がある時に |

## Example Review Output

```
## Quality Review: F4 Lecture QA

### Critical Issues
- None

### High Issues
1. **lecture_bm25_store.py:45**: Missing type hint for `_build_index()` return value
   - Fix: Add `-> BM25` type hint

2. **lecture_answerer_service.py:78**: Deep nesting (4 levels)
   - Fix: Use early return pattern

### Medium Issues
1. **lecture_qa_service.py**: File exceeds 400 lines (currently 512)
   - Consider: Extract verify_answer() to separate module

### Summary
- Coding Principles: 85% compliant
- Type Hints: 92% coverage
- Design: Follows existing patterns
```

## Key Points

1. **並列実行**: 3人のレビュアーが同時に実行される
   - 効率的なレビュー
   - 異なる視点からのフィードバック

2. **レポート永続化**: すべてのレビュー結果をドキュメントに保存
   - 後から参照可能
   - 改善のトレース

3. **優先順位**: Critical/High を優先
   - ブロッカーを最初に解消
   - Medium/Low はバックログ

4. **反復**: 修正後に再度レビュー可能
   - 改善を確認
   - 完了まで繰り返し

## Commands Reference

```bash
# Run team review
/team-review

# Read review reports
ls .claude/docs/research/review-*.md

# Fix issues and verify
uv run pytest
uv run ruff check .
uv run ty check

# All checks
poe all
```

## Checklist

- [ ] 実装が完了している
- [ ] `/team-review` を実行
- [ ] レビューレポートを確認
- [ ] Critical/High 問題を修正
- [ ] すべてのテストがパス
- [ ] `ruff check` & `ty check` がパス
- [ ] カバレッジ 80%+
