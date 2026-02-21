# Procedure PDF Ingest Script

`procedure_index` へ PDF 文書を投入するための CLI スクリプトです。  
このプロジェクトでは、これがそのまま F2 手続きQAの RAG 知識投入になります。

## 対象スクリプト

- `scripts/procedure_index_ingest/ingest_procedure_pdf.py`

## 何をするか

1. PDF からテキスト抽出（`pypdf`）
2. テキストをチャンク分割
3. `procedure_index` 用ドキュメントに整形
4. Azure AI Search に `merge_or_upload_documents` で投入

## 前提

- `AZURE_SEARCH_ENDPOINT`
- `AZURE_SEARCH_API_KEY`
- （任意）`PROCEDURE_SEARCH_INDEX_NAME`  
  未指定時は `procedure_index`

依存:

- `azure-search-documents`（プロジェクト既存）
- `pypdf`（必要）

`pypdf` が未導入の場合:

```bash
uv add pypdf
```

## 基本コマンド

### 1) まず dry-run（投入せず解析だけ）

```bash
uv run python scripts/procedure_index_ingest/ingest_procedure_pdf.py \
  --input /path/to/pdfs \
  --dry-run
```

### 2) 実投入

```bash
uv run python scripts/procedure_index_ingest/ingest_procedure_pdf.py \
  --input /path/to/pdfs
```

### 3) 単一PDFを投入

```bash
uv run python scripts/procedure_index_ingest/ingest_procedure_pdf.py \
  --input /path/to/manual.pdf
```

### 4) 第一段階RAG動作テスト用データを使う

`scripts/procedure_index_ingest/input` のPDF群をそのまま使います。

```bash
# 解析のみ
uv run python scripts/procedure_index_ingest/ingest_procedure_pdf.py \
  --phase1-test \
  --dry-run

# 実投入
uv run python scripts/procedure_index_ingest/ingest_procedure_pdf.py \
  --phase1-test
```

## 主なオプション

- `--input` : PDFファイルまたはディレクトリ（必須）
- `--phase1-test` : `scripts/procedure_index_ingest/input` を入力として使用
- `--index-name` : インデックス名上書き
- `--chunk-size` : 1チャンクの最大文字数（default: `800`）
- `--chunk-overlap` : チャンク重なり（default: `120`）
- `--batch-size` : 1回のアップロード件数（default: `100`）
- `--glob` : ディレクトリ走査パターン（default: `*.pdf`）
- `--max-files` : 処理ファイル数上限
- `--skip-index-setup` : index の create/update をスキップ
- `--dry-run` : Azureへ投入せず解析だけ

## 生成される Search フィールド

- `source_id` (key)
- `title`
- `section`
- `snippet`
- `content`
- `page`
- `chunk_no`
- `file_name`
- `source_path`
- `lang`
- `updated_at`

## 実装との対応

`app/services/procedure_retrieval_service.py` の Retriever は次を優先して読みます:

- `source_id`
- `title`
- `section`
- `snippet`
- （fallbackで `content/text/body/summary_text`）

このスクリプトの出力は上記に適合しています。

## 典型運用

1. `--dry-run` でチャンク数を確認
2. 問題なければ本投入
3. `POST /api/v4/procedure/ask` で検索ヒットを確認

## トラブルシュート

- `Missing endpoint` / `Missing API key`:
  - 環境変数または `--endpoint` / `--api-key` を指定
- `No text chunks extracted`:
  - PDFが画像のみの可能性（OCR前処理が必要）
- `failed > 0`:
  - Azure Search 側のフィールド不整合やサイズ制限を確認
