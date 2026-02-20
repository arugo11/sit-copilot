# Azure を CLI で新規構築して、SIT Copilot 開発環境を整えた話

_Date: 2026-02-20_

## TL;DR

SIT Copilot の仕様（`docs/SPEC.md`）に合わせて、Azure リソースを **CLI 主導で新規作成** しました。  
最終的に、以下を作成・接続できる状態にしています。

- Resource Group
- Key Vault
- Storage Account
- Azure AI Search
- Azure AI Speech
- Azure AI Vision
- Azure OpenAI
- Application Insights

加えて、実装ブートストラップ用に `.env.azure.generated` を生成し、秘密情報は Key Vault に保存しました。

---

## 背景と目的

このプロジェクトは MVP 段階ですが、F1/F2/F4 の実装を進めるには Azure 側の接続情報が必要です。  
「どの段階からキーが必要か」は以前整理済みで、今回はその前提を踏まえて、**実際に使える開発環境を先に作る**ことを目的にしました。

狙いは 2 つです。

1. 実装を止めないためのインフラ先行準備
2. 人が再現できる CLI 手順の確立

---

## 作成したリソース（実績）

サブスクリプション: `Azure サブスクリプション 1`  
リージョン: `japaneast`  
リソースグループ: `rg-sitcopilot-dev-02210594`

- Key Vault: `kvsitc02210594`
- Storage: `stsitc02210594`
- Search: `srchsitc02210594`
- Speech: `speech-sitc-02210594`
- Vision: `vision-sitc-02210594`
- OpenAI: `aoai-sitc-02210594`
- App Insights: `appi-sitc-02210594`

---

## 実施フロー（時系列）

### 1. Azure CLI 実行基盤の確立

環境に `az` コマンドが入っていなかったため、`uv tool run` 経由で Azure CLI を起動しました。  
途中で依存衝突があったため、最終的に以下で安定化しました。

- `azure-cli==2.74.0`
- Python 3.10
- `setuptools<81`

### 2. `az login --use-device-code` で認証

ブラウザ認証（Device Code）でログインし、ターゲットサブスクリプションへ切り替えました。

### 3. Resource Provider 登録

初回構築時に `MissingSubscriptionRegistration` が発生したため、先に Provider を登録しました。

- `Microsoft.KeyVault`
- `Microsoft.CognitiveServices`
- `Microsoft.Search`
- `Microsoft.Storage`
- `Microsoft.Insights`
- `Microsoft.OperationalInsights`

### 4. リソース作成（最小コスト寄り）

MVP の立ち上げ速度を重視し、SKU は低コスト寄りを選択しました。

- Speech: `F0`
- Vision: `F0`
- Search: `free`
- OpenAI: `S0`（利用可能範囲で作成）

### 5. Key Vault へのシークレット保存

Key Vault が RBAC モードだったため、`set-policy` は使わず、ロール割り当てで対応しました。

- 付与ロール: `Key Vault Secrets Officer`

保存したシークレット:

- `azure-speech-key`
- `azure-vision-key`
- `azure-search-key`
- `azure-storage-key`
- `azure-openai-key`
- `applicationinsights-connection-string`

### 6. ローカル起動用 `.env` 生成

開発を止めないため、`.env.azure.generated` を生成しました。  
このファイルには接続情報・キーが含まれるため、**機密ファイルとして扱う**前提です。

### 7. 後片付け

途中試行で残った空の Resource Group を削除し、本命環境だけを残しました。

---

## つまずきポイントと解決

### 1. `az: command not found`

- 原因: Azure CLI 未導入
- 対応: `uv tool run` で CLI を実行

### 2. `MissingSubscriptionRegistration`

- 原因: Provider 未登録
- 対応: `az provider register` を先行実施

### 3. Key Vault 名バリデーションエラー

- 原因: 命名規則違反（英数字制約）
- 対応: 命名フォーマットを短い英数字へ修正

### 4. `ForbiddenByRbac` で secret set 失敗

- 原因: RBAC 権限不足
- 対応: Vault スコープで `Key Vault Secrets Officer` を割り当て

### 5. Application Insights 作成時の競合

- 原因: `Microsoft.OperationalInsights` 未登録
- 対応: Provider 登録後に再作成

---

## この作業で得た学び

1. Azure 初期構築は「リソース作成」より「前提整備（Provider/RBAC）」が重要。  
2. Key Vault は access policy と RBAC で運用が全く異なる。  
3. 失敗ログを見て即座に手順へ反映すると、再実行でほぼ必ず前進できる。  
4. `.env` を作る場合でも、Key Vault を正とした二層運用にしておくと安全性と実装速度を両立しやすい。

---

## 今後の実装接続ポイント

- `app/core/config.py` に Azure 用設定キーを追加
- Speech トークン発行 API（`/api/v4/auth/speech-token`）の実装
- Vision OCR サービスの接続
- Search インデックス（`procedure_index`, `lecture_index`）接続
- OpenAI 呼び出しサービス実装とモデルデプロイ連携

---

## 参考（公式）

- Azure CLI: https://learn.microsoft.com/en-us/cli/azure/
- Provider: https://learn.microsoft.com/en-us/cli/azure/provider?view=azure-cli-latest
- Cognitive Services: https://learn.microsoft.com/en-us/cli/azure/cognitiveservices/account?view=azure-cli-latest
- Key Vault Secret: https://learn.microsoft.com/en-us/cli/azure/keyvault/secret?view=azure-cli-latest
- Role Assignment (RBAC): https://learn.microsoft.com/en-us/cli/azure/role/assignment?view=azure-cli-latest
- Search Service: https://learn.microsoft.com/en-us/cli/azure/search/service?view=azure-cli-latest
- Storage Account: https://learn.microsoft.com/en-us/cli/azure/storage/account?view=azure-cli-latest
- Application Insights: https://learn.microsoft.com/en-us/cli/azure/monitor/app-insights/component?view=azure-cli-latest
