# Azure OpenAI 設定ガイド

## 概要

RAGシステムを動作させるには、Azure OpenAI Service の API キーとエンドポイントを設定する必要があります。

## 手順 1: Azure OpenAI リソースの作成

### 1.1 Azure Portal にアクセス

1. https://portal.azure.com にログイン
2. 検索バーで「Azure OpenAI」を検索
3. 「Azure OpenAI」を選択

### 1.2 新規リソースの作成

**リソースが既にある場合は、「手順 2」へスキップ**

1. 「作成」ボタンをクリック
2. 以下の情報を入力:
   - **サブスクリプション**: 使用するサブスクリプションを選択
   - **リソースグループ**: 新規または既存のリソースグループを選択
   - **リソース名**: 一意な名前を入力（例: sit-copilot-openai）
   - **地域**: 選択可能な地域を選択（推奨: Japan East または East US）
   - **価格レベル**: Standard S0
3. 「次へ: ネットワーク」→「次へ: タグ」→「次へ: 確認と作成」
4. 「作成」をクリック
5. デプロイが完了するまで待機（通常5-15分）

## 手順 2: API キーとエンドポイントの取得

### 2.1 リソースにアクセス

1. Azure Portal で作成した Azure OpenAI リソースを開く
2. 左側のメニューから「リソース管理」→「キーとエンドポイント」を選択

### 2.2 必要な情報をコピー

以下の情報をメモします：

1. **API キー**:
   - 「キー 1」または「キー 2」の「キー」をコピー
   - 「表示」アイコンをクリックすると確認できます

2. **エンドポイント**:
   - 「エンドポイント」の URL をコピー
   - 例: `https://sit-copilot-openai.openai.azure.com/`

3. **リソース名**:
   - エンドポイント URL からドメイン名部分を抽出
   - 例: `sit-copilot-openai`

### 2.3 モデルデプロイの確認（オプション）

1. 左側のメニューから「リソース管理」→「モデルデプロイ」を選択
2. `gpt-4o` または `gpt-4` モデルがデプロイされているか確認
3. デプロイがない場合:
   - 「デプロイの作成」→「ベースモデル」を選択
   - `gpt-4o` を選択してデプロイ

## 手順 3: 環境変数の設定

### 3.1 設定ファイルの作成

テンプレートをコピーして設定ファイルを作成します：

```bash
cp .env.azure.generated.template .env.azure.generated
```

### 3.2 設定ファイルの編集

`.env.azure.generated` ファイルを編集し、Azure Portal から取得した値を入力します：

```bash
# Azure OpenAI API Key
AZURE_OPENAI_API_KEY=pasted-api-key-here

# Azure OpenAI Endpoint (末尾のスラッシュを含める)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Azure OpenAI Account Name (エンドポイントのドメイン部分)
AZURE_OPENAI_ACCOUNT_NAME=your-resource-name

# Azure OpenAI Model (デプロイしたモデル名)
AZURE_OPENAI_MODEL=gpt-4o

# Azure OpenAI を有効化
AZURE_OPENAI_ENABLED=true
```

### 3.3 設定の確認

以下のコマンドで設定を確認します：

```bash
cat .env.azure.generated
```

## 手順 4: 動作確認

### 4.1 サーバーを再起動

```bash
# 既存のサーバーを停止
pkill -f uvicorn

# サーバーを起動
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 4.2 テストスクリプトの実行

```bash
uv run python /tmp/test_rag.py
```

正常に動作している場合、回答は以下のようになります：

**期待される動作（Azure OpenAI が有効）**:
```
📝 回答:
機械学習は人工知能の一分野であり、コンピュータにデータから
学習する能力を与える技術です。[00:05]で説明されています。
代表的手法としては、教師あり学習、教師なし学習、
強化学習の三つがあります。

📊 信頼度: high

✓ 検証結果: 主張はすべて講義資料に裏付けられています。
```

**現在の動作（Azure OpenAI が無効）**:
```
📝 回答:
講義資料では「〜」および「〜」の内容が関連しています。

📊 信頼度: low

✓ 検証結果: 回答生成に失敗したため、資料から直接抜粋しました。
```

## トラブルシューティング

### エラー: "azure_openai_answer_network_error"

**原因**: Azure OpenAI エンドポイントにアクセスできない

**解決策**:
1. `.env.azure.generated` の `AZURE_OPENAI_ENDPOINT` が正しいか確認
2. API キーが有効か確認
3. ネットワーク接続を確認

### エラー: "Unauthorized" (401)

**原因**: API キーが無効または間違っている

**解決策**:
1. Azure Portal で API キーを再生成
2. `.env.azure.generated` のキーを更新
3. サーバーを再起動

### エラー: "Deployment not found"

**原因**: 指定したモデルがデプロイされていない

**解決策**:
1. Azure Portal でモデルデプロイを確認
2. `AZURE_OPENAI_MODEL` をデプロイ名に合わせる
3. 必要に応じてモデルをデプロイ

## 関連リンク

- [Azure OpenAI Service ドキュメント](https://learn.microsoft.com/ja-jp/azure/ai-services/openai/)
- [Azure Portal](https://portal.azure.com)
- [価格表](https://azure.microsoft.com/ja-jp/pricing/details/cognitive-services/openai-service/)

---

**作成日**: 2026-02-22
**バージョン**: 1.0
