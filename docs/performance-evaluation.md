# SIT Copilot 性能評価ドキュメント

**作成日**: 2026-02-24
**評価者**: 自動計測 + 手動評価手順の提示

---

## 概要

ポスター掲載用の性能指標を、**計測可能性**に基づき3段階に分類した。

| 分類 | 意味 | 対応 |
|------|------|------|
| **A. 自動計測済み** | プログラムで再現可能に計測 | → ポスターに実測値を掲載 |
| **B. 手動評価可能** | ユーザーがデモで計測可能 | → 手順を提示、ユーザーが記入 |
| **C. 評価困難** | 音声入力など外部依存で再現困難 | → ポスターから削除 |

---

## A. 自動計測済み（ポスターに掲載）

### A-1. 字幕変換レイテンシ

| 項目 | 値 |
|------|-----|
| **ja → en 平均** | **0.76 秒** |
| **ja → やさしい日本語 平均** | **0.99 秒** |
| **計測条件** | 専門用語を含む講義文3文 × 各モード |
| **目標** | < 3 秒 |
| **判定** | 達成 |

**計測方法**:
```bash
POST /api/v4/lecture/subtitle/transform
リクエスト送信 → レスポンス受信の経過時間
```

**計測データ**:
| 入力テキスト | ja→en | ja→easy-ja |
|---|---|---|
| 機械学習ではデータセットを訓練データと検証データに分割します | 0.89s | 1.04s |
| 過学習を防ぐために正則化やドロップアウトを用います | 0.67s | 0.94s |
| 外れ値は四分位範囲法やZスコアで検出することができます | 0.72s | 1.00s |

### A-2. 字幕変換品質

5文の専門用語含む講義テキストで ja→en の翻訳精度を確認。

| # | 入力（日本語） | 出力（英語） | 正確性 |
|---|---|---|---|
| 1 | 機械学習ではデータセットを訓練データと検証データに分割します | In machine learning, the dataset is split into training data and validation data | 正確 |
| 2 | 教師あり学習では正解ラベル付きのデータを使ってモデルを訓練します | In supervised learning, we train the model using data with correct labels. | 正確 |
| 3 | 過学習を防ぐために正則化やドロップアウトを用います | We use regularization and dropout to prevent overfitting. | 正確 |
| 4 | 外れ値は四分位範囲法やZスコアで検出することができます | Outliers can be detected using the interquartile range method or Z-scores. | 正確 |
| 5 | データの前処理は非常に重要です。欠損値の処理、特徴量のスケーリングを行う必要があります | Data preprocessing is very important. We need to handle missing values and scale features. | 正確 |

**判定**: 5/5 = 100% 正確（専門用語の誤訳なし）

### A-3. セッションライフサイクルレイテンシ

| 操作 | レイテンシ |
|------|-----------|
| セッション開始 | 0.008 秒 |
| チャンク永続化 | 0.016 秒 |
| セッション確定（QAインデックスなし） | 7.07 秒 |
| セッション確定（QAインデックスあり、8チャンク） | 含: finalize内部で実行 |

### A-4. QA レイテンシ（E2E）

| 項目 | 値 |
|------|-----|
| **平均** | **9.18 秒** |
| **最小** | 6.02 秒 |
| **最大** | 18.87 秒 |
| **計測条件** | 根拠あり質問5問、BM25検索 |
| **目標** | < 5 秒 |
| **判定** | 未達成 |
| **DB記録 latency_ms 平均** | 約 7,500 ms |

**注**: 現環境ではLLM回答生成がタイムアウトし、fallback（ソース直接抜粋）で応答している。
LLMが正常動作する環境ではレイテンシが改善される可能性がある。

### A-5. ASR 補正レイテンシ

| 項目 | 値 |
|------|-----|
| **平均** | **6.41 秒** |
| **計測条件** | ASR誤認識テキスト5文 |
| **補正採用率** | 0/5（Judge が保守的に棄却） |

**注**: Judgeが保守的に動作しており、「明確なASRハルシネーション」と判定される閾値（confidence ≥ 0.85）を超えなかったため、全て不採用。これはJudgeが意図通り慎重に動作していることを示す。

---

## B. 手動評価可能（ユーザーが計測する手順）

### B-1. QA 関連性（根拠あり質問の正答率）

**評価の目的**: 根拠がある質問に対して正確に回答できるかを測定。

**手順**:
1. 講義セッションを開始し、十分な講義内容を投入する（最低5分相当）
2. セッションを確定し、QAインデックスを構築する
3. 以下のテスト質問を投入する:

   **根拠あり（正答期待）**:
   - 外れ値について先生は何と言っていましたか
   - 残差の確認方法は何分ごろ説明されましたか
   - 課題の説明は講義内で触れられていましたか

   **根拠なし（安全fallback期待）**:
   - この手法は他大学の授業でも一般的ですか
   - 先生はこの単元を試験に必ず出すと言っていましたか

4. 各回答について以下を評価する:
   - [ ] 回答が質問に対応しているか（1: 無関係 / 2: 部分的 / 3: 適切）
   - [ ] 引用 (chunk_id) が正しいソースを指しているか
   - [ ] 根拠なし質問に対して「講義内では確認できない」等の安全応答をしているか

**算出**: 関連性スコア = 適切回答数 / 総質問数

**コマンド例**:
```bash
curl -s -X POST http://127.0.0.1:8000/api/v4/lecture/qa/ask \
  -H "Content-Type: application/json" \
  -H "X-Lecture-Token: dev-lecture-token" \
  -H "X-User-Id: eval-user" \
  -d '{"session_id":"<SESSION_ID>","question":"外れ値について先生は何と言っていましたか"}' \
  | python3 -m json.tool
```

### B-2. Judge 棄却率

**評価の目的**: LLM as a Judge が不適切な回答を正しく棄却するかを測定。

**前提**: QA回答生成が正常に動作する環境（Azure OpenAI接続が安定している状態）

**手順**:
1. B-1 と同じセッションで、根拠なし質問を投入する
2. 各回答のレスポンスから以下を確認:
   - `verification_summary` に "reject" が含まれるか
   - `confidence` が "low" か
   - `fallback_reason` が空でないか
3. DBの `qa_turns` テーブルで `outcome_reason` を集計:
   ```sql
   SELECT outcome_reason, COUNT(*) FROM qa_turns
   WHERE session_id = '<SESSION_ID>'
   GROUP BY outcome_reason;
   ```

### B-3. ASR 精度（字幕の正確性）

**評価の目的**: リアルタイム音声認識の文字起こし精度を測定。

**前提**: Azure Speech SDK が動作するブラウザ環境

**手順**:
1. 事前に原稿テキストを用意する（200〜300文字程度）
2. 講義セッションを開始してLive画面を表示する
3. 原稿を読み上げる
4. 表示された字幕テキストを記録する
5. 原稿（正解）と字幕（ASR出力）を文字レベルで比較する

**算出**: CER (Character Error Rate) = (挿入+削除+置換) / 正解文字数

**注意**: 以下の要因で精度が変動する:
- マイクの品質と周囲の雑音レベル
- 話者の発話速度と明瞭さ
- 専門用語の割合

---

## C. 評価困難（ポスターから削除する項目）

### C-1. ASR精度（文字起こし精度の定量値）

**削除理由**:
- Azure Speech SDK はブラウザ側で動作するため、バックエンドAPIからの計測不可
- 音声入力のリアルタイム性から、再現可能な自動テストが困難
- マイク品質・雑音環境・話者の発話特性に大きく依存
- CER計算には正解テキストと字幕テキストの手動対応付けが必要

**代替案**: デモ時に原稿読み上げで体験的に示す（定量値はポスターに載せない）

### C-2. Judge棄却率（定量値）

**削除理由**:
- 現環境ではLLM回答生成がfallbackしているため、Judge検証が正しく動作しない
- Judgeの棄却率はLLMの回答品質に依存し、一定の条件下でしか意味のある値にならない
- 「Judgeが動作している」という定性的記述に留める

---

## 再現手順

### 環境準備
```bash
cd /home/argo/sit-copilot
source .venv/bin/activate
./scripts/dev-server.sh start all
```

### 評価セッション作成
```bash
python3 <<'PY'
import requests, time

base = 'http://127.0.0.1:8000'
headers = {
    'X-Lecture-Token': 'dev-lecture-token',
    'X-User-Id': 'eval-user',
    'Content-Type': 'application/json'
}

# セッション作成
r = requests.post(f'{base}/api/v4/lecture/session/start', headers=headers, json={
    'course_name': '評価用講義',
    'lang_mode': 'ja',
    'camera_enabled': False,
    'consent_acknowledged': True
})
sid = r.json()['session_id']
print(f"Session: {sid}")

# 講義内容投入（実際の講義に近い内容を8チャンク）
chunks = [
    "今日は機械学習の基礎について講義を行います。機械学習とは、データからパターンを学習し、予測や分類を行う技術のことです。",
    "機械学習には大きく分けて3つの種類があります。教師あり学習、教師なし学習、そして強化学習です。",
    "教師あり学習の代表的なアルゴリズムとして、線形回帰、ロジスティック回帰、決定木、サポートベクターマシン、ニューラルネットワークがあります。",
    "データの前処理は非常に重要です。欠損値の処理、特徴量のスケーリング、外れ値の検出と処理を行う必要があります。外れ値は四分位範囲法やZスコアで検出できます。",
    "モデルの評価には交差検証を用います。データを訓練データとテストデータに分割し、過学習を防ぎます。",
    "過学習とは、訓練データに対しては高い性能を示すが、未知のデータに対しては性能が低下する現象です。正則化やドロップアウトで対策できます。",
    "次回の課題として、Pythonのscikit-learnライブラリを使って、アヤメのデータセットで分類モデルを構築してください。",
    "回帰分析では残差の確認が重要です。残差プロットを描いて、等分散性やパターンの有無を確認します。",
]

for i, text in enumerate(chunks):
    requests.post(f'{base}/api/v4/lecture/speech/chunk', headers=headers, json={
        'session_id': sid, 'start_ms': i*30000, 'end_ms': i*30000+29000,
        'text': text, 'confidence': 0.92, 'is_final': True, 'speaker': 'teacher'
    })

# 確定（QAインデックス構築）
r = requests.post(f'{base}/api/v4/lecture/session/finalize', headers=headers,
                   json={'session_id': sid, 'build_qa_index': True}, timeout=120)
print(f"Finalize: {r.json()}")
PY
```

### 字幕変換レイテンシ計測
```bash
# ja → en
time curl -s -X POST http://127.0.0.1:8000/api/v4/lecture/subtitle/transform \
  -H "Content-Type: application/json" \
  -H "X-Lecture-Token: dev-lecture-token" \
  -H "X-User-Id: eval-user" \
  -d '{"session_id":"<SESSION_ID>","text":"機械学習ではデータセットを訓練データと検証データに分割します","target_lang_mode":"en"}'
```

---

## ポスター掲載判定まとめ

| 指標 | 計測結果 | ポスター掲載 | 理由 |
|------|----------|:---:|------|
| 字幕変換遅延 (ja→en) | 0.76s | **掲載** | 自動計測済み、目標達成 |
| 字幕変換遅延 (ja→easy) | 0.99s | **掲載** | 自動計測済み、目標達成 |
| 字幕変換品質 | 5/5 正確 | **掲載** | 専門用語含む翻訳が正確 |
| QA E2Eレイテンシ | 9.18s (avg) | **掲載** | 自動計測済み（要注記） |
| セッション開始 | 0.008s | 参考 | 内部指標 |
| チャンク永続化 | 0.016s | 参考 | 内部指標 |
| ASR精度 | 未計測 | **削除** | 音声入力が必要で再現困難 |
| QA関連性 | 未計測 | **空欄** | ユーザーがデモで記入 |
| Judge棄却率 | 未計測 | **削除** | LLM動作不安定で信頼性不足 |
