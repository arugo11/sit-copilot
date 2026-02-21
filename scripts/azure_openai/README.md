# Azure OpenAI Preflight Check

Azure OpenAI の `endpoint/deployment` 設定不整合を API 実行前に検出するためのスクリプトです。

## 対象

- `scripts/azure_openai/preflight_check.py`

## 何を確認するか

1. 設定バリデーション
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_ACCOUNT_NAME`
- `AZURE_OPENAI_MODEL`
2. endpoint 正規化
- `*.api.cognitive.microsoft.com` + `AZURE_OPENAI_ACCOUNT_NAME` の場合  
  `https://<account>.openai.azure.com` に正規化
3. deployment 到達性
- 軽量 `chat/completions` リクエストで到達可否を判定

## 使い方

```bash
set -a
source .env.azure.generated
set +a

uv run python scripts/azure_openai/preflight_check.py
```

## 結果の見方

- `config_valid=true` かつ `probe_result=pass`: 実行可能
- `config_valid=false`: 設定不備（`reason=` を確認）
- `probe_result=fail`:
  - `probe_failure=deployment_not_found`: deployment 名不一致
  - `probe_failure=endpoint_not_found`: endpoint 不正
  - `probe_failure=auth_failed`: API key 権限/キー不一致
  - `probe_failure=network_error`: DNS/ネットワーク問題

## 推奨運用

1. `preflight_check.py` を PASS させる
2. `AZURE_SEARCH_ENABLED=true` で `/api/v4/procedure/ask` を実行
3. `fallback=""` かつ `sources` 非空を確認

## 注意

- `.env.azure.generated` は機密情報を含むためコミットしないでください。
- `AZURE_OPENAI_MODEL` は deployment 名です。モデル名の一般名詞ではありません。
