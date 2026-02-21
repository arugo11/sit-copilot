# Work Log: Researcher

## Summary

F1 Azure OpenAI Summary Integration のための包括的なリサーチを実施。Azure OpenAI chat completion API、日本語テキスト処理、構造化出力、エビデンス帰属、トークン最適化、エラーハンドリングに関するベストプラクティスを調査。F4の既存パターンを再利用可能な形で整理。

## Tasks Completed

- [x] **Azure OpenAI chat completion API for Japanese text summarization**: gpt-4oモデル、APIバージョン2024-10-21、temperature=0での要約ベストプラクティスを特定
- [x] **Best practices for lecture/meeting summarization prompts**: システムプロンプト、ユーザープロンプトテンプレート、JSON出力形式のパターンを調査
- [x] **Evidence attribution patterns in LLM responses**: F4の引用形式（type/timestamp/text）を再利用可能、RAGコンテキストでの検証パターンを確認
- [x] **Token counting and cost optimization strategies**: tiktokenライブラリ、日本語1.2-1.5トークン/文字、事前計算の重要性を特定
- [x] **Similar lecture summarization implementations**: 構造化出力機能（JSON schema）とエラーハンドリングパターンを調査

## Sources Consulted

### Azure OpenAI Documentation
- [How to use structured outputs](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs) - gpt-4o対応、APIバージョン2024-10-21
- [Chat completions API](https://learn.microsoft.com/ja-jp/azure/cognitive-services/openai/how-to/chatgpt) - 日本語ドキュメント
- [Azure AI Foundry models](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models) - モデルカタログ
- [Quota management](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/quota) - レート制限

### Token & Cost Optimization
- [Token概念讲解](https://www.xmsumi.com/detail/2098) - トークンの基本概念
- [Python API真实成本](https://m.blog.csdn.net/LogicNest/article/details/152936958) - コスト分析
- [Token管理艺术](https://m.blog.csdn.net/m0_72606794/article/details/156464631) - 最適化戦略

### Prompt Engineering
- [LLM指令微调：文本摘要](https://m.blog.csdn.net/qq_36803941/article/details/140154236) - テキスト要約プロンプト
- [Advanced RAG Techniques](https://tool.lu/ru_RU/article/5SG/detail) - RAGと引用
- [GraphRAG综述](https://blog.csdn.net/2301_79985417/article/details/147349058) - グラフベースRAG

### Error Handling
- [解决RateLimitError](https://m.php.cn/faq/1816131.html) - レート制限ソリューション
- [Spring AI RetryClient](https://m.blog.csdn.net/weixin_45422672/article/details/148851722) - リトライパターン

## Key Findings

### 1. Azure OpenAI API (2025)
- **最新API**: Responses API（chat completionsとassistantsの統合）
- **推奨バージョン**: `2024-10-21`（GA）
- **モデル**: `gpt-4o`（2024-11-20または2024-08-06）
- **構造化出力**: `response_format: {"type": "json_object"}` でJSON強制

### 2. 日本語テキスト処理
- **トークン比**: 日本語は1.2-1.5トークン/文字（英語の1.5-2倍のコスト）
- **ツール**: `tiktoken` ライブラリで事前カウントが必須
- **要約パラメータ**: temperature=0（事実性重視）、max_tokens=800-1500

### 3. エビデンス帰属（Evidence Attribution）
- **F4パターン再利用可能**: `{"type": "speech|visual", "timestamp": "MM:SS", "text": "..."}`
- **F1拡張**: source_typeに `speech|slide|board` を追加
- **Verifierパターン**: Claim-by-claim検証、JSON出力

### 4. プロンプトエンジニアリング
- **システムプロンプト**: 日本語要約の専門家ロールを明示
- **JSON出力指定**: 「JSON形式で返してください」をシステムメッセージに含める
- **マルチソース対応**: 発言・スライド・板書を分けて構造化

### 5. エラーハンドリング
- **429エラー**: 指数関数的バックオフでリトライ
- **F1要件**: Azure無効時はERROR（フォールバックなし、F4とは異なる）
- **レート制限**: 1-10秒間隔で評価（分単位ではない）

### 6. コスト最適化
- **事前フィルタリング**: 不要なコンテンツをAPI呼び出し前に削除
- **max_tokens適正設定**: 過剰割り当て回避
- **日本語最適化**: 簡潔な表現、冗長な命令を排除

## Files Saved

- `/home/argo/sit-copilot/.claude/docs/research/f1-azure-openai-summary.md` - 包括的なリサーチ結果
- `/home/argo/sit-copilot/.claude/docs/libraries/azure-openai-summary.md` - Azure OpenAIライブラリ制約ドキュメント

## Communication with Teammates

- → **Architect**: リサーチ完了を通知。F4パターンの再利用可能性、JSONスキーマ設計、マルチソース統合、エラーハンドリングの方針を共有。

## Issues Encountered

- **gemini CLIのrate limit**: Gemini CLIが使用できなかったため、WebSearchで代用（十分な情報を取得）

## Recommendations for Architect

1. **LectureSummaryService設計**: F4のLectureAnswererServiceパターンをベースに、要約特化のプロンプトとJSONスキーマを設計
2. **JSONスキーマ定義**: `summary`（400字以内）+ `key_points`（3-5個、各100字以内）の構造
3. **マルチソース統合**: `source_type: speech|slide|board` で各ソースをタグ付け
4. **エラーハンドリング**: Azure無効時は `LectureSummaryError` 例外を送出（フォールバックなし）
5. **構造化出力**: `response_format: {"type": "json_object"}` でJSON強制
6. **トークン管理**: `tiktoken` で事前カウント、コスト監視

---

**Research completed. Ready for design phase.**
