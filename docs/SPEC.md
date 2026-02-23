# 技術仕様書 最終版 v4.0

## SIT Course Access Copilot

留学生, 障がい学生の履修ハードルを下げる, 講義前後一体型マルチモーダル学習支援Webアプリ
日本語モードでは日本人学生も利用可能

## 0. 変更要約

v3からの変更は次です.

* F3, キャンパス移動案内を削除
* 対象ユーザーに日本人学生を追加, 日本語モードで通常利用可能
* 仕様をAI-Agent実装向けに詳細化

  * データモデル
  * API契約
  * Azureホスティング
  * 非機能要件
  * 実装順序
  * テスト条件

---

## 1. 目的と設計方針

### 1.1 目的

このアプリの目的は, 講義の前, 中, 後を一つの流れで支援することです.

* 履修前, その授業を追えそうか判断しやすくする
* 講義中, 字幕, 板書, スライドを統合して理解負荷を下げる
* 講義後, 実際の講義発言を根拠に質問できるようにする

### 1.2 主対象と一般利用

主対象は留学生, 障がい学生です. ただし, UIや機能は一般化し, 日本語モードでは日本人学生も通常の講義補助として使える設計にします.

重要な設計方針として, ユーザーに障がい情報の入力を必須にしません. 支援は属性ベースではなく, 利用設定ベースで提供します.

### 1.3 MVP方針

MVPでは, 実動デモを最優先にします.

* 学内公式システムとのSSO連携はしない
* 手入力と資料アップロードで成立する
* 講義データは1回分セッション単位で完結
* まず source-only QA を高品質にする

---

## 2. 機能一覧

本仕様で実装する機能は4つです.

* F0, 履修前サポート, Course Readiness Check
* F1, 講義中マルチモーダル補助, Multimodal Lecture Assist
* F4, 講義後QA, Transcript-native Lecture QA
* F2, 学内手続きQA, Procedure Guide

削除済み

* F3, キャンパス移動案内

---

## 3. ユーザーと利用モード

## 3.1 ユーザー種別

実装上はロールを細かく分けません. MVPでは全員同じUIを使います.

* student, 主利用者
* teacher, 将来拡張, MVPでは授業ノート確認のみ
* support_staff, 将来拡張, MVPでは未実装

## 3.2 言語モード

全画面で共通です.

* `ja`, 日本語
* `easy-ja`, やさしい日本語
* `en`, 英語

## 3.3 利用プリセット

障がい情報を聞かずに使えるよう, プリセットで設定を切り替えます.

* `standard`, 日本人学生向け標準
* `international`, 留学生向け, 字幕と用語説明を強め
* `accessibility`, 支援向け, 文字サイズ大, 高コントラスト, 読み上げ導線強化

プリセットは任意で, いつでも切替可能です.

---

## 4. 画面構成

Webアプリは4画面構成です.

* `/readiness`, 履修前サポート
* `/lecture/live`, 講義中補助
* `/lecture/qa`, 講義後QA
* `/procedure`, 学内手続きQA

共通レイアウト

* 上部ヘッダ, アプリ名, 言語モード, 文字サイズ, プリセット
* 左ナビ, 4画面リンク
* 右上, 設定
* 下部, エラー通知トースト

---

## 5. 機能詳細仕様

# 5.1 F0, 履修前サポート

## 5.1.1 目的

履修前に, その科目の難所と必要な支援設定を示し, 履修ハードルを下げる.

## 5.1.2 入力

必須

* 科目名
* シラバス本文 or シラバスPDF
* 言語モード

任意

* 初回講義資料PDF
* 自己申告日本語読解レベル, 1-5
* 自己申告分野経験, 1-5

## 5.1.3 出力

必須

* `readiness_score`, 0-100
* `terms`, 10-20語
* `difficult_points`, 2-5件
* `recommended_settings`, 2-5件
* `prep_tasks`, 2-5件
* `disclaimer`, 目安であり履修可否判定ではない

## 5.1.4 処理ルール

* シラバスから, 授業目標, キーワード, 評価方法, 進行形式を抽出
* 初回資料がある場合, 用語頻度を加算
* 難所推定はルールベースを先に適用

  * 数式記号頻度が高い, 板書多め候補
  * 評価方法が口頭発表含む, 発表支援候補
  * 前提科目の記載が多い, 前提知識要求高め候補
* LLMは説明文整形と用語説明生成のみ
* スコアはルールベースで算出し, LLMに数値決定をさせない

## 5.1.5 完了条件

* 5秒以内応答
* 出力項目欠落なし
* 不足入力時も暫定出力を返す

---

# 5.2 F1, 講義中マルチモーダル補助

## 5.2.1 目的

音声だけでは抜けやすい情報を, 板書, スライドOCRで補い, 30秒単位で理解補助を出す.

## 5.2.2 入力

必須

* `session_id`
* マイク音声
* カメラ映像, 1台
* ROI設定

  * `slide_roi`
  * `board_roi`

任意

* 講義スライドPDF
* 科目名
* 言語モード

## 5.2.3 カメラ利用範囲

許可

* 投影スクリーン
* 黒板, ホワイトボード
* 教員の手元資料の一部

禁止

* 学生席全景の保存
* 顔追跡
* 常時動画保存

## 5.2.4 リアルタイム処理仕様

### 音声

* フロントでAzure Speech SDKを使って認識
* 部分字幕を画面表示
* 確定字幕のみバックエンドへ送信
* 送信単位, 5秒チャンク or 確定イベント単位

### 映像

* フロントで1fpsキャプチャ
* ROIごとに差分判定
* OCR送信は2秒に1回上限
* 差分小なら送信スキップ
* 画像はJPEG圧縮で送信, 長辺1280px以内

### OCR

* バックエンドがAzure AI Vision OCRを呼ぶ
* OCR結果に信頼度を付与
* 低信頼度行は破棄
* OCRイベントを保存

### 要約

* 30秒ごとに更新
* 参照窓は直近60秒
* 根拠種別タグを必須付与

  * `speech`
  * `slide`
  * `board`

## 5.2.5 講義中UIの表示項目

* リアルタイム字幕
* 30秒要約
* 用語カード
* 根拠タグ
* 映像品質状態
* 音声中心モード表示, フォールバック時

## 5.2.6 フォールバック

* OCR品質低下時, 音声中心モードへ切替
* 音声信頼度低下時, 要約更新を一時保留
* どちらも低い時, 講義補助精度低下を表示

## 5.2.7 授業終了時に生成する成果物

* 授業ノート
* 重要語一覧
* 復習質問候補
* 講義後QA用インデックスデータ

---

# 5.3 F4, 講義後QA

## 5.3.1 目的

講義後に, 実際の講義発言, 板書, スライドを根拠として質問に答える. 一般知識の説明ではなく, その授業で何が言われたかを返す.

## 5.3.2 モード

MVPでは `source-only` を標準に固定します.

* `source-only`

  * 講義セッション内の根拠のみ使用
  * 根拠がない場合は答えない
* `source-plus-context`

  * Phase2, 講義外の補足説明を追加可能

## 5.3.3 入力

* `session_id`
* `question`
* `lang_mode`
* `mode`, デフォルト `source-only`
* `followup_context_id`, 任意

## 5.3.4 出力

必須

* `answer`
* `confidence`, `high|medium|low`
* `citations`, 1-3件
* `answer_scope`, `lecture-session-only`
* `suggested_followups`, 1-3件
* `fallback`, ある場合のみ

citationには時刻情報を必須で入れます.

## 5.3.5 質問の範囲

答える

* 講義中に教員が発言した内容
* 板書の文字情報
* スライドに書かれていた用語, 箇条書き
* 課題説明が講義内に出ていたかどうか
* 何分ごろ説明されたか

答えない

* 講義で触れていない一般知識
* 成績予想
* 教員の意図推測
* 講義外の事務情報

## 5.3.6 検索と回答の処理順

1. 質問を正規化
2. セッションフィルタで lecture_index を検索
3. 上位8件取得
4. 再ランキング
5. source-only用LLMで回答生成
6. Verifierで根拠一致検証
7. citation整形
8. 回答返却

## 5.3.7 回答ルール

* 回答長は1-4文
* 断定は根拠がある部分のみ
* 推測禁止
* citationなし回答禁止
* `講義内では確認できない` を返してよい

## 5.3.8 フォローアップ質問

* 直前3問まで文脈保持
* 直前回答のcitationを参照して短い質問を解決
* セッションを跨がない

---

# 5.4 F2, 学内手続きQA

## 5.4.1 目的

学内手続きの質問に対して, 公式文書を根拠に回答する.

## 5.4.2 入力

* `query`
* `lang_mode`

## 5.4.3 出力

* `answer`
* `confidence`
* `sources`
* `action_next`
* `fallback`

## 5.4.4 制約

* 根拠なし回答禁止
* 日時, 締切は確認導線付き
* sourcesが空なら `fallback` を返す

---

## 6. データモデル定義

AI-Agent向けに, 実装する永続データを固定します.

## 6.1 ストレージ構成

MVPでは以下を採用します.

* 構造化データ, SQLite, SQLAlchemy, Azure Filesマウントで永続化
* ファイル, Azure Blob Storage
* 検索インデックス, Azure AI Search
* メトリクス/ログ, Application Insights

注意点

* SQLiteを使う都合上, demo環境のAPIコンテナは1レプリカ固定
* 将来の複数レプリカ化はPostgreSQL移行で対応

## 6.2 エンティティ一覧

* `users`
* `courses`
* `lecture_sessions`
* `speech_events`
* `visual_events`
* `summary_windows`
* `lecture_chunks`
* `qa_turns`
* `procedure_doc_chunks`
* `app_settings`

## 6.3 テーブル定義

以下は実装時の最低カラムです. 型はSQLAlchemyでこの通り定義します.

### `users`

```json id="7hpolr"
{
  "id": "uuid",
  "display_name": "string",
  "preferred_lang": "ja|easy-ja|en",
  "ui_preset": "standard|international|accessibility",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### `courses`

```json id="pjhezy"
{
  "id": "uuid",
  "user_id": "uuid",
  "course_name": "string",
  "syllabus_blob_path": "string|null",
  "syllabus_text": "text|null",
  "default_lang_mode": "ja|easy-ja|en",
  "created_at": "datetime"
}
```

### `lecture_sessions`

```json id="s80ffb"
{
  "id": "string, session_id",
  "user_id": "uuid",
  "course_id": "uuid|null",
  "course_name": "string",
  "lang_mode": "ja|easy-ja|en",
  "status": "active|finalized|error",
  "camera_enabled": "bool",
  "slide_roi": "[x1,y1,x2,y2]|null",
  "board_roi": "[x1,y1,x2,y2]|null",
  "started_at": "datetime",
  "ended_at": "datetime|null",
  "qa_index_built": "bool",
  "consent_acknowledged": "bool"
}
```

### `speech_events`

```json id="6v7ru2"
{
  "id": "string",
  "session_id": "string",
  "start_ms": "int",
  "end_ms": "int",
  "text": "text",
  "confidence": "float",
  "is_final": "bool",
  "speaker": "teacher|unknown",
  "created_at": "datetime"
}
```

### `visual_events`

```json id="2ap3pp"
{
  "id": "string",
  "session_id": "string",
  "timestamp_ms": "int",
  "source": "slide|board",
  "ocr_text": "text",
  "ocr_confidence": "float",
  "quality": "good|warn|bad",
  "change_score": "float",
  "blob_path": "string|null",
  "created_at": "datetime"
}
```

### `summary_windows`

```json id="s3r2r0"
{
  "id": "string",
  "session_id": "string",
  "start_ms": "int",
  "end_ms": "int",
  "summary_text": "text",
  "key_terms_json": "json string",
  "evidence_event_ids_json": "json string",
  "created_at": "datetime"
}
```

### `lecture_chunks`

これはSQLiteにも保存し, 同時にAzure AI Searchにも入れます.

```json id="vq7l72"
{
  "id": "string",
  "session_id": "string",
  "chunk_type": "speech|visual|merged",
  "start_ms": "int",
  "end_ms": "int",
  "speech_text": "text|null",
  "visual_text": "text|null",
  "summary_text": "text|null",
  "keywords_json": "json string",
  "embedding_text": "text",
  "indexed_to_search": "bool",
  "created_at": "datetime"
}
```

### `qa_turns`

```json id="7d7wzi"
{
  "id": "string",
  "session_id": "string|null",
  "feature": "lecture_qa|procedure_qa",
  "question": "text",
  "answer": "text",
  "confidence": "high|medium|low",
  "citations_json": "json string",
  "retrieved_chunk_ids_json": "json string",
  "latency_ms": "int",
  "verifier_supported": "bool",
  "created_at": "datetime"
}
```

---

## 7. Azureホスティング構成

この項目は実装固定です. AI-Agentはこの構成を前提に実装してください.

## 7.1 採用Azureサービス

* Azure Static Web Apps, フロントエンドホスト
* Azure Container Apps, FastAPI APIホスト
* Azure Container Apps, Workerホスト, 同一環境内の別コンテナでも可
* Azure OpenAI, 要約, QA, Verifier, 翻訳, 用語説明
* Azure AI Speech, リアルタイム音声認識, 読み上げ
* Azure AI Vision, OCR
* Azure AI Search, `procedure_index`, `lecture_index`
* Azure Blob Storage, アップロード資料, 任意の切り出し画像
* Azure Files, SQLite永続ボリューム
* Azure Key Vault, 秘密情報
* Azure Application Insights, 監視

## 7.2 ホスト構成

* Frontend, Azure Static Web Apps
* API, Azure Container Apps, 外部公開HTTPS
* Worker, Azure Container Apps, 内部実行
* SQLiteファイル, Azure FilesをAPIコンテナにマウント
* フロントはAPIをHTTPSで呼び出す

## 7.3 環境

* `dev`
* `demo`

`demo` 環境では,

* APIレプリカ数は1固定
* SQLite永続化を使う
* データ更新は手動のみ
* デモ前日に動作確認して凍結

## 7.4 セキュリティ設定

* CORSはStatic Web Appsドメインのみ許可
* すべてHTTPS
* APIキーはKey Vault参照
* フロントに秘密鍵を持たせない
* Speechトークンはバックエンドから短命トークン発行

---

## 8. バックエンド構成

実装言語は Python 3.11, FastAPI で固定します.

## 8.1 ディレクトリ構成

AI-Agentは以下の構成で生成してください.

```text id="1o7v6w"
backend/
  app/
    main.py
    core/
      config.py
      logging.py
      errors.py
      security.py
    db/
      base.py
      models.py
      session.py
      migrations/
    schemas/
      common.py
      readiness.py
      lecture_live.py
      lecture_qa.py
      procedure.py
    routers/
      health.py
      settings.py
      readiness.py
      lecture_session.py
      lecture_live.py
      lecture_qa.py
      procedure.py
      auth_tokens.py
    services/
      speech_ingest_service.py
      vision_ocr_service.py
      lecture_summary_service.py
      lecture_index_builder.py
      lecture_search_service.py
      lecture_qa_service.py
      procedure_retrieval_service.py
      procedure_qa_service.py
      verifier_service.py
      translation_service.py
      blob_service.py
      ai_search_service.py
      openai_service.py
    prompts/
      readiness_prompts.py
      lecture_summary_prompts.py
      lecture_qa_prompts.py
      verifier_prompts.py
      procedure_qa_prompts.py
    workers/
      finalize_session_worker.py
      procedure_ingest_worker.py
    utils/
      text_normalize.py
      time_window.py
      image_quality.py
      diff_score.py
  tests/
    unit/
    integration/
  requirements.txt
```

## 8.2 実装責務

* RouterはHTTP入出力のみ
* Serviceは業務ロジック
* Prompt定義は `prompts/` に隔離
* Azure SDK呼び出しは `*_service.py` に閉じる
* DBモデルとPydanticスキーマを分離

---

## 9. フロントエンド構成

実装は React + TypeScript で固定します.

## 9.1 ディレクトリ構成

```text id="162vqz"
frontend/
  src/
    app/
      routes.tsx
      App.tsx
    pages/
      ReadinessPage.tsx
      LectureLivePage.tsx
      LectureQAPage.tsx
      ProcedurePage.tsx
    components/
      common/
      lecture/
      readiness/
      qa/
      procedure/
    hooks/
      useSpeechRecognizer.ts
      useLectureSession.ts
      usePollingSummary.ts
      useCameraOCR.ts
    services/
      apiClient.ts
      speechTokenClient.ts
    stores/
      settingsStore.ts
      lectureStore.ts
    types/
      api.ts
    utils/
      roi.ts
      text.ts
```

## 9.2 フロント実装ルール

* 講義中字幕はフロント側で即時描画
* バックエンド反映失敗時も字幕表示は継続
* OCR送信は `useCameraOCR` で制御
* 要約は5秒ごとポーリング
* 講義後QAのcitationは時刻表示を目立たせる
* アクセシビリティ設定はローカル保存 + サーバ保存

---

## 10. API仕様 v4

Base pathは固定です.

```text id="1gx8wb"
/api/v4
```

## 10.1 共通エラー応答

全APIで共通です.

```json id="j7sgmq"
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

HTTPステータス

* 200, 正常
* 400, 入力不正
* 404, 対象なし
* 409, 状態不整合
* 500, 内部エラー

---

# 10.2 共通設定

## GET `/api/v4/settings/me`

ユーザー設定取得

## POST `/api/v4/settings/me`

ユーザー設定更新

Request

```json id="j56pi8"
{
  "preferred_lang": "ja",
  "ui_preset": "standard",
  "font_size": "medium",
  "high_contrast": false,
  "tts_enabled": false
}
```

---

# 10.3 Speechトークン

## GET `/api/v4/auth/speech-token`

Azure Speech SDK用の短命トークンを返す.

Response

```json id="h41prr"
{
  "token": "string",
  "region": "japaneast",
  "expires_in_sec": 540
}
```

---

# 10.4 F0, 履修前サポート

## POST `/api/v4/course/readiness/check`

Request

```json id="pg27kg"
{
  "course_name": "統計学基礎",
  "syllabus_text": "授業の目的は...",
  "first_material_blob_path": null,
  "lang_mode": "ja",
  "jp_level_self": 3,
  "domain_level_self": 2
}
```

Response

```json id="ji5izz"
{
  "readiness_score": 68,
  "terms": [
    {"term": "回帰分析", "explanation": "変数どうしの関係を式で表す方法"}
  ],
  "difficult_points": [
    "板書で式変形が多い可能性",
    "口頭説明の比率が高い可能性"
  ],
  "recommended_settings": [
    "字幕ON",
    "板書OCRON",
    "やさしい日本語要約"
  ],
  "prep_tasks": [
    "回帰分析の基本用語を10分確認",
    "分散と標準偏差を復習"
  ],
  "disclaimer": "この結果は履修準備の目安です. 履修可否を判定するものではありません."
}
```

---

# 10.5 F1, 講義セッション

## POST `/api/v4/lecture/session/start`

Request

```json id="sqplgz"
{
  "course_name": "統計学基礎",
  "course_id": null,
  "lang_mode": "ja",
  "camera_enabled": true,
  "slide_roi": [100, 80, 900, 520],
  "board_roi": [80, 560, 920, 980],
  "consent_acknowledged": true
}
```

Response

```json id="mx55qz"
{
  "session_id": "lec_20260301_001",
  "status": "active"
}
```

## POST `/api/v4/lecture/speech/chunk`

確定字幕イベントを保存する.

Request

```json id="mc22xb"
{
  "session_id": "lec_20260301_001",
  "start_ms": 15000,
  "end_ms": 20000,
  "text": "外れ値がある場合は散布図で確認します.",
  "confidence": 0.93,
  "is_final": true,
  "speaker": "teacher"
}
```

## POST `/api/v4/lecture/visual/event`

OCR対象ROIの画像を送る. バックエンドでOCR実行.

Request, `multipart/form-data`

* `session_id`, string
* `timestamp_ms`, int
* `source`, `slide|board`
* `change_score`, float
* `image`, jpeg file

Response

```json id="jlwmz4"
{
  "event_id": "v_021",
  "ocr_text": "外れ値, 残差確認",
  "ocr_confidence": 0.82,
  "quality": "good"
}
```

## GET `/api/v4/lecture/summary/latest?session_id=...`

最新の30秒要約を返す. 未生成なら生成して返す.

Response

```json id="kplw90"
{
  "session_id": "lec_20260301_001",
  "window_start_ms": 120000,
  "window_end_ms": 180000,
  "summary": "この区間では, 外れ値の影響と散布図での確認方法を説明していた.",
  "key_terms": [
    {"term": "外れ値", "evidence_tags": ["speech", "board"]}
  ],
  "evidence": [
    {"type": "speech", "ref_id": "t_034"},
    {"type": "board", "ref_id": "v_021"}
  ],
  "status": "ok"
}
```

## POST `/api/v4/lecture/session/finalize`

講義終了処理, ノート生成, インデックス生成まで実行する.

Request

```json id="xgm44m"
{
  "session_id": "lec_20260301_001",
  "build_qa_index": true
}
```

Response

```json id="zrs9nm"
{
  "session_id": "lec_20260301_001",
  "status": "finalized",
  "note_generated": true,
  "qa_index_built": true,
  "stats": {
    "speech_events": 124,
    "visual_events": 39,
    "summary_windows": 18,
    "lecture_chunks": 22
  }
}
```

## DELETE `/api/v4/lecture/session/{session_id}`

講義セッションを削除する. `active/live` は自動で `finalize` 後に削除する.
削除対象にはセッション本体と関連イベント, 要約, チャンク, `speech_review_histories` を含む.

Response

```json
{
  "session_id": "lec_20260301_001",
  "status": "deleted",
  "auto_finalized": true
}
```

---

# 10.6 F4, 講義後QA

## POST `/api/v4/lecture/qa/ask`

Request

```json id="v027r9"
{
  "session_id": "lec_20260301_001",
  "question": "外れ値について先生は何と言っていましたか.",
  "lang_mode": "easy-ja",
  "mode": "source-only"
}
```

Response

```json id="cbzg1f"
{
  "answer": "講義では, 外れ値があると回帰の線が大きく動くことがあるので, 先に散布図で確認すると説明していました.",
  "confidence": "high",
  "citations": [
    {
      "type": "speech",
      "start_ms": 172000,
      "end_ms": 181000,
      "snippet": "外れ値が1点入るだけで直線がかなり動くので..."
    },
    {
      "type": "board",
      "timestamp_ms": 174000,
      "snippet": "外れ値, 残差確認"
    }
  ],
  "answer_scope": "lecture-session-only",
  "suggested_followups": [
    "残差の説明はどこでありましたか.",
    "課題との関係は説明されていましたか."
  ],
  "fallback": ""
}
```

## POST `/api/v4/lecture/qa/followup`

Request

```json id="om8qe4"
{
  "session_id": "lec_20260301_001",
  "followup_context_id": "qa_ctx_001",
  "question": "それは課題にも関係しますか.",
  "lang_mode": "ja"
}
```

---

# 10.7 F2, 学内手続きQA

## POST `/api/v4/procedure/ask`

Request

```json id="m7ixrn"
{
  "query": "在学証明書はどこで発行できますか.",
  "lang_mode": "ja"
}
```

Response

```json id="ei710k"
{
  "answer": "在学証明書は証明書発行機で申請できます.",
  "confidence": "high",
  "sources": [
    {
      "title": "証明書発行案内",
      "section": "申請方法",
      "snippet": "在学証明書は証明書自動発行機で...",
      "source_id": "doc_012_c03"
    }
  ],
  "action_next": "学生証を持って証明書発行機を利用してください. 発行時間は窓口案内も確認してください.",
  "fallback": ""
}
```

---

## 11. AI処理仕様

AI-Agentが実装で迷いやすい部分を固定します.

## 11.1 モデル役割分割

* `ReadinessAnalyzer`, F0の説明文整形
* `LectureSummarizer`, F1の30秒要約
* `LectureQAAnswerer`, F4 source-only回答
* `ProcedureAnswerer`, F2回答
* `Verifier`, F2/F4共通の根拠一致検証
* `Simplifier`, easy-ja変換
* `Translator`, en変換

## 11.2 LLM共通ルール

全LLM呼び出しで守るルールです.

* 根拠にない断定をしない
* 事実と推測を混ぜない
* 出力JSONはスキーマ厳守
* citation必須の場面で citationなし出力を返さない
* F4 source-onlyでは一般知識の補足禁止

## 11.3 F1 要約の優先順位

* 講義の流れ, `speech_events` 優先
* 用語表記, `slide OCR` 優先
* 数式, 箇条書き, `board OCR` 優先
* OCR信頼度しきい値未満は不採用

  * slide, 0.75
  * board, 0.68

## 11.4 F4 Lecture QAの検索仕様

### lecture_indexの検索単位

* `merged chunk`, 30秒単位を主
* 補助で `speech chunk`, `visual chunk` を持つ

### 検索方法

* キーワード + ベクトルのハイブリッド検索
* `session_id` で必ずフィルタ
* 上位8件取得, 上位4件を再ランキング
* 再ランキング後の4件のみ回答器に渡す

## 11.5 Verifier仕様

### 入力

* 質問
* 回答案
* citations
* candidate_chunks

### 検証

* 回答の主要名詞句がchunkに存在するか
* citationの時刻がchunk範囲内か
* snippetがchunkテキストに含まれるか
* source-onlyで講義外情報が混ざっていないか

### 失敗時

* 1回だけ短く再生成
* 再失敗なら `fallback` を返す

---

## 12. 検索インデックス仕様

Azure AI Searchは2本に分けます.

* `procedure_index`
* `lecture_index`

## 12.1 lecture_index スキーマ

以下のフィールドを必須にします.

* `chunk_id`, key
* `session_id`, filterable
* `course_name`, searchable, filterable
* `date`, filterable
* `chunk_type`, filterable
* `start_ms`, filterable, sortable
* `end_ms`, filterable, sortable
* `speech_text`, searchable
* `visual_text`, searchable
* `summary_text`, searchable
* `keywords`, searchable, filterable
* `embedding`, vector
* `lang`, filterable

## 12.2 インデックス投入タイミング

* F1の `finalize` 実行時に生成
* 同期処理で完了確認を返す
* 失敗時は `qa_index_built=false` で返し, 再実行可能

---

## 13. 非機能要件

## 13.1 レイテンシ

* F0 readiness, 5秒以内
* F1 字幕表示, 2.5秒以内
* F1 要約更新, 10秒以内
* F4 講義後QA, 5秒以内
* F2 手続きQA, 6秒以内

## 13.2 可用性

* demo環境で30分デモ中, 致命エラー0回
* API失敗時, 1回再試行
* F1 OCR失敗時, 音声中心モード継続
* F4根拠不足時, fallbackで安全に終了

## 13.3 プライバシー

* 生映像, 生音声の保存はデフォルトOFF
* 保存するのは字幕, OCRテキスト, 要約, citation snippet
* 画像保存時は人物領域ぼかし
* 講義開始時に同意確認必須
* セッションデータ保持30日, 期限後削除
* 障がい情報の入力, 保存は必須にしない

## 13.4 アクセシビリティ

* キーボード操作対応
* フォーカス可視化
* 文字サイズ3段階
* 高コントラスト
* 色だけで状態を表現しない
* 全回答に読み上げ導線

## 13.5 監視

Application Insightsで最低限監視する指標

* APIレイテンシ
* エラー率
* OCR成功率
* F4 citationなし回答の発生数
* finalize失敗率

---

## 14. ログ仕様

実験と考察用に, ログ項目を固定します.

保存する

* `request_id`
* `feature`
* `session_id`
* `timestamp`
* `latency_ms`
* `model_name`
* `prompt_version`
* `retrieved_chunk_ids`
* `verifier_supported`
* `citations`
* `confidence`
* `user_feedback`, 任意

保存しない

* 生音声
* 生動画
* 個人の障がい種別

---

## 15. 評価設計

コンペの採点を意識して, 技術指標と利用指標の両方を持ちます.

## 15.1 技術指標

### F1

* WER
* 専門語認識率
* 板書反映率
* 要約事実一致率
* 根拠タグ一致率

### F4

* QA正答率
* citation一致率
* 根拠なし回答率, 目標0
* 講義外質問の適切拒否率
* フォローアップ成功率

### F2

* 根拠一致率
* 根拠なし回答率, 目標0

## 15.2 利用指標

* 履修意向変化, F0利用前後
* 初回講義理解の自己評価
* 復習時間短縮
* 講義後QA利用率, 24時間以内

---

## 16. AI-Agent向け実装順序

この順で実装すると, 途中でもデモ可能です.

1. バックエンド基盤, FastAPI, DB, 設定, ヘルスチェック
2. F2, Procedure QA, 先にRAGを完成
3. F1, 音声イベント保存 + 字幕表示
4. F1, OCRイベント保存
5. F1, 30秒要約生成
6. F1, finalize処理
7. lecture_index生成 + Azure AI Search投入
8. F4, source-only QA
9. F0, Readiness Check
10. UI調整, アクセシビリティ
11. 評価ログと集計画面

---

## 17. 受け入れ条件, 完了判定

AI-Agentの実装完了条件として, 以下を満たすこと.

## 17.1 機能完了

* F0, F1, F4, F2 がエンドツーエンドで動作
* F4の回答に必ずcitationが付く
* F3のコード, UI, APIは存在しない
* 日本語モードで日本人学生が追加設定なしで利用できる

## 17.2 データ完了

* `lecture_sessions`, `speech_events`, `visual_events`, `summary_windows`, `lecture_chunks`, `qa_turns` が保存される
* `finalize` 後に `lecture_index` 検索可能

## 17.3 安全完了

* 生音声, 生映像がデフォルト保存されない
* 同意なしで講義開始できない
* source-only QAで根拠なし回答が出ない

---

## 18. デモシナリオ, 最終版

3分デモの構成も固定しておきます.

* 0:00-0:25, F0 履修前サポート, 用語と推奨設定
* 0:25-1:15, F1 講義中補助, 字幕 + 板書 + スライド
* 1:15-2:05, F4 講義後QA, 発言を根拠に回答, citation時刻表示
* 2:05-2:35, F2 手続きQA, 根拠付き回答
* 2:35-3:00, 指標, ログ, 改善結果

F4の citation時刻付き回答が, この最終版の見せ場です.

---

## 19. 実装上の注意, AI-Agent向け

最後に, 実装で崩れやすい点だけ固定します.

* F4は必ず `session_id` 指定を必須にする
* F4の回答器には検索上位4件だけ渡す
* LLMにスコア計算をさせない
* OCR失敗は例外にせず, `quality=bad` で記録する
* `finalize` は冪等にする, 同じセッションで再実行可能
* demo環境はSQLiteのためAPIレプリカ数1固定
* 将来拡張を見越しても, まず source-only QA を優先する

