# frontend.md

## 0. この文書の役割

講義支援アプリのフロントエンド実装仕様を固定するための文書です.
対象は AI-Agent と実装者です.
ここに書いていない挙動は実装しないでください.
曖昧な点が出たら, 本文の優先順位に従って判断します.

優先順位は, 1) アクセシビリティ要件, 2) 講義中の可読性, 3) 講義後の根拠付きQA, 4) デモ映え, 5) 実装コストです.

### 0.1 現実装ステータス(2026-02-22)

- 本MVPはログイン不要デモとして実装済み
- `/operator/session` は今回スコープ外
- ストリーミングは `StreamClient` 抽象I/F を導入し, 実装は `MockStreamTransport` で駆動
- `WebSocketTransport` / `SseTransport` は将来接続の骨組みのみ実装
- `live` は partial/final 字幕カード, Sourceタブ, Assist要点/用語, 再接続状態表示に対応
- `review` は `qa.answer.chunk` 単位で回答ブロックを段階追加し, `done` で確定
- `sources` は type/keyword フィルタと 0件時 EmptyState 置換に対応
- `settings` は `GET/POST /api/v4/settings/me` 契約で保存し, `transcriptDensity`/`autoScrollDefault` を保持
- dev環境のAPI既定は同一オリジン(`VITE_API_BASE_URL`未設定時) + Vite proxy でCORS依存を減らす

---

## 1. 対象プロダクトの前提

### 1.1 目的

外国人留学生, 障がいのある学生, 日本語話者の学生を含めて, 同じ講義を補助付きで受けられるようにする.
講義中は字幕, 翻訳, 板書/投影資料の取り込みを表示する.
講義後は, 講義発言と資料を根拠にした質問対応を行う.

### 1.2 対象ユーザー

- 学生
  - 留学生
  - 障がいのある学生
  - 日本語学生(日本語UIを選べば通常の講義補助として利用)
- 教員またはTA(デモ時の入力確認のみ)
- 運営(デモ時の講義セッション管理)

### 1.3 本仕様で扱う範囲

- WebアプリのUI/UX
- コンポーネント仕様
- 画面遷移
- 状態管理
- アクセシビリティ
- 多言語UI
- Azure上のフロントエンドホスト方針

### 1.4 本仕様で扱わない範囲

- モデル学習
- バックエンドの内部推論ロジック
- キャンパス移動案内(削除済み)

---

## 2. 先行例から採用する設計方針

### 2.1 Fluent系で寄せる理由

Azureで構成するので, 見た目もMicrosoft系の文脈に寄せるとデモの一体感が出る.
ただし完全コピーはしない. 使うのは設計原則と寸法の考え方だけ.

採用する点

- 4px基準のspacingスケール
- token駆動で色, 余白, 角丸, 影, タイポを管理
- 角丸は 4 / 8 / 12 を中心に使う
- 大きい画面での情報密度を保ちながら, ブレークポイントで再配置する
- モーションは短く, 役割を持つものだけに限定する

### 2.2 AI UI系の先行例から採用する点

講義後QAや講義中の非同期処理は, 普通のフォームUIよりも AI UI の状態表現が重要になる.
そのため, 進行中, ストリーミング中, 中断, エラー, 再試行を明示する設計を採用する.

採用する点

- loading中の視覚表示だけで終わらせず, スクリーンリーダー向けのlive region通知を出す
- 非同期で項目が追加/削除された後のfocus位置を固定する
- 失敗時は赤いアイコンだけで済ませず, 文言で理由を出す

### 2.3 ダッシュボード系の先行例から採用する点

講義一覧, 文字起こし, QA履歴, ソース参照はデータ中心の画面になる.
そのため, 空状態, 読み込み, 結果0件の画面を最初から設計する.

採用する点

- tableやリストのempty stateは, 元の要素を消してメッセージに置き換える
- skeletonはカード, リスト, テーブルにだけ使う
- ボタンやモーダル全体にはskeletonを使わない

---

## 3. 技術スタック(フロントエンド)

### 3.1 実装技術

- React 18 + TypeScript
- Vite
- Tailwind CSS
- shadcn/ui + Radix UI
- TanStack Query
- TanStack Table
- TanStack Virtual
- Zustand
- react-router
- react-hook-form + zod
- i18next
- Framer Motion
- WebSocket client(または Azure Web PubSub / SignalR クライアント)

### 3.2 ホスト方針(Azure)

本アプリのフロントエンドは Azure でホストする.

推奨構成

- 本番/デモ配信: Azure Static Web Apps
- カスタムドメインと入口統合: Azure Front Door(必要ならWAF有効)
- 認証連携: 将来拡張(MVPデモでは未実装)
- 監視: Azure Application Insights(JavaScript SDK)
- CI/CD: GitHub Actions -> Azure Static Web Apps

理由

- SPAの配信が簡単で, デモ用のPreview環境を切りやすい
- TLS, CDN, デプロイ導線を短くできる
- Azureで統一した説明がしやすい

### 3.3 想定ブラウザ

- Chrome 最新2版
- Edge 最新2版
- Safari 最新2版
- Firefox 最新2版

---

## 4. 情報設計(IA)と画面遷移

### 4.1 画面一覧

```text
/                       ランディング兼デモ開始導線
/lectures               講義一覧
/lectures/:id/live      講義中ビュー(字幕, 翻訳, 資料, 板書)
/lectures/:id/review    講義後レビュー(文字起こし, 要約, 根拠付きQA)
/lectures/:id/sources   ソース一覧(板書OCR, 投影資料OCR, 音声区間)
/settings               表示設定, 言語, アクセシビリティ
/operator/session       今回MVPスコープ外(将来拡張)
```

### 4.2 基本遷移

- 初回は `/` から入る
- 講義を選ぶと `/lectures/:id/live`
- 講義終了後, 自動でレビュー導線を強く出して `/lectures/:id/review`
- review画面から根拠の元発言へ戻れる
- どの画面からでも `/settings` を開ける(モーダルでも別画面でも可, 初版はサイドシート推奨)

### 4.3 導線の優先順位

講義中は迷わせない.
最上位は次の3つだけを常時見せる.

- 字幕/翻訳
- いま映っている資料や板書
- すぐ使える補助操作(文字サイズ, 言語, 速度, コントラスト)

講義後は次の3つを前面に出す.

- 質問する
- 根拠を見る
- 自分用メモを残す(任意)

---

## 5. レイアウト仕様

### 5.1 グリッド

- デスクトップは12カラム
- タブレットは8カラム
- モバイルは4カラム
- ベース余白は4pxスケールで管理
- 画面左右marginは viewportで可変

### 5.2 ブレークポイント

```ts
export const BREAKPOINTS = {
  sm: 320,
  md: 480,
  lg: 640,
  xl: 1024,
  xxl: 1366,
  xxxl: 1920,
} as const
```

運用ルール

- 320-639px は縦積み1カラム
- 640-1023px は2カラム中心
- 1024px以上は3ペインを許可
- 1366px以上はライブ画面を3ペイン標準にする

### 5.3 主要レイアウトパターン

#### A. 講義中ビュー(推奨, デスクトップ)

```text
┌──────────────────────────────────────────────┐
│ TopBar: 講義名 | 接続状態 | 言語 | 字幕設定 | ... │
├───────────────┬──────────────────┬───────────┤
│ 左ペイン      │ 中央ペイン       │ 右ペイン    │
│ 資料/板書     │ 字幕+翻訳         │ 質問補助     │
│ スナップショット│ タイムライン      │ 用語, 要点   │
│ OCR結果       │ 話者ラベル         │ 状態通知     │
├───────────────┴──────────────────┴───────────┤
│ 下部ミニバー: 録音/処理状態, 遅延, 再接続, ヘルプ │
└──────────────────────────────────────────────┘
```

#### B. 講義中ビュー(タブレット)

- 左の資料ペインを折りたたみ可能にする
- 右の補助ペインはタブ化する
- 中央の字幕は常に残す

#### C. モバイル

- 1カラム
- 上部にセグメント切替
  - 字幕
  - 資料
  - 補助
- 字幕は常時ピクチャインピクチャ風の小窓を許可(任意)

---

## 6. デザインシステム仕様

### 6.1 デザイントークン定義

実装は CSS Variables で定義し, Tailwind から参照する.
ハードコード禁止.

```css
:root {
  /* color */
  --bg-page: 248 250 252;
  --bg-surface: 255 255 255;
  --bg-muted: 241 245 249;
  --fg-primary: 15 23 42;
  --fg-secondary: 71 85 105;
  --fg-inverse: 255 255 255;
  --accent: 37 99 235;
  --accent-weak: 219 234 254;
  --success: 22 163 74;
  --warning: 217 119 6;
  --danger: 220 38 38;
  --border: 226 232 240;
  --focus: 37 99 235;

  /* radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-pill: 999px;

  /* spacing, 4px base */
  --sp-1: 4px;
  --sp-2: 8px;
  --sp-3: 12px;
  --sp-4: 16px;
  --sp-5: 20px;
  --sp-6: 24px;
  --sp-8: 32px;
  --sp-10: 40px;
  --sp-12: 48px;

  /* shadow */
  --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.06);
  --shadow-md: 0 6px 20px rgba(15, 23, 42, 0.10);
  --shadow-lg: 0 12px 32px rgba(15, 23, 42, 0.14);

  /* motion */
  --dur-fast: 120ms;
  --dur-base: 180ms;
  --dur-slow: 240ms;
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
}
```

### 6.2 テーマ

必須テーマ

- light
- dark
- high-contrast

要件

- light/dark切替は即時反映
- high-contrastは設定画面で明示ON
- contrast不足の色をデモ用に固定色でごまかさない

### 6.3 タイポグラフィ

フォント方針

- Windows系は `Segoe UI` を優先
- macOS/iOSは system font
- 日本語は `BIZ UDPGothic` または `Noto Sans JP` をフォールバック
- 等幅は `ui-monospace`

推奨スケール

```ts
export const typeScale = {
  caption:  { size: 12, line: 16, weight: 400 },
  body:     { size: 14, line: 20, weight: 400 },
  bodyStrong:{ size: 14, line: 20, weight: 600 },
  sub:      { size: 16, line: 22, weight: 600 },
  h3:       { size: 20, line: 28, weight: 600 },
  h2:       { size: 24, line: 32, weight: 600 },
  h1:       { size: 32, line: 40, weight: 600 },
}
```

運用ルール

- 英語UIラベルは sentence case
- 日本語UIは短く切る
- 講義字幕のデフォルト文字サイズは 18px, 行間 1.5
- 字幕はユーザー設定で 14px-32px の範囲で変更可能

### 6.4 角丸と境界線

- ボタン, 入力, タブは 8px
- カード, パネルは 12px
- 小バッジは 4px
- 1つの連結コンポーネント内では, 角丸のつなぎ目に不自然な隙間を作らない

### 6.5 アイコン

- 単色線画を基本にする
- 状態の強調時だけ fillアイコンを許可
- 12pxアイコンは情報表示専用, クリック不可
- クリック対象アイコンは 16px以上, hit area は最低 32px, 推奨 40px以上

---

## 7. モーション仕様(デモ映えを出すが, やりすぎない)

### 7.1 モーション原則

- 役割がある時だけ動かす
- 画面全体を横に滑らせない
- 大きい領域の画面遷移はフェード中心
- 列挙項目は軽いstaggerで入れる(最大80ms差)
- 連続で再描画される字幕行にはアニメーションを入れない

### 7.2 使うアニメーション

- ページ切替: fade(120-180ms)
- サイドシート: enter/exit + 少しのelevation
- カード追加: fade + y 4-8px
- 通知トースト: fade + scale 0.98 -> 1
- ライブ状態pill: 色変化のみ, 点滅は禁止

### 7.3 reduced motion対応

- `prefers-reduced-motion: reduce` を検知したら, 全モーションを 0-40ms に短縮
- 動きで伝えている情報は, テキスト状態でも伝える
- 設定画面にも `アニメーションを減らす` を出し, OS設定より優先しない(表示だけの上書きは可)

---

## 8. 画面別の詳細仕様

## 8.1 `/` ランディング兼デモ開始

### 目的

- アプリの用途を1画面で伝える
- 講義一覧に入る
- デモ映えするが, 説明過多にしない

### レイアウト

- 左 60%: アプリ説明, デモスクリーンショット(自動スライド禁止)
- 右 40%: デモ開始ボタン, 言語選択
- モバイルは縦積み

### 必須要素

- キャッチコピー(1行)
- 対応対象(留学生, 障がい者, 日本語学生)
- 主要機能3つ
- `デモを開始`(ログイン不要)
- 言語切替(ja/en)

---

## 8.2 `/lectures` 講義一覧

### 目的

- 進行中/終了済みのデモセッションに最短で入る
- デモ用に一覧の視認性を高くする

### レイアウト

- 上部: 状態フィルタ, デモセッション開始ボタン
- 中央: カード一覧(デスクトップ3列, タブレット2列, モバイル1列)
- localStorageに保存したデモセッションを表示

### 講義カード仕様

```ts
type LectureCard = {
  session_id: string
  course_name: string
  started_at: string
  status: "live" | "ended"
  readiness_score?: number
}
```

カードUI

- コース名
- session_id
- 開始時刻
- 状態pill
- CTA
  - live中なら `講義に入る`
  - endedなら `レビューを見る`
  - live中は `セッション終了` ボタンも表示

### 状態表示

- 初回ロード: localStorageから即時表示（0件時はempty state）
- 0件: empty state
  - 文言: APIからまだセッションが作成されていないことを書く
  - CTA: デモセッション開始

---

## 8.3 `/lectures/:id/live` 講義中ビュー(最重要)

### 目的

講義中の理解補助を, 1画面で止まらず提供する.
この画面が審査デモの主役.

### レイアウト(デスクトップ標準)

#### TopBar

左から順に

- 学講義名(長い場合は省略, hoverで全体)
- 接続状態pill
- 処理遅延表示(例: `字幕 1.2s`)
- 言語切替
- 字幕表示設定
- 文字サイズ
- コントラスト
- ヘルプ
- ユーザーメニュー

#### 左ペイン, `SourcePanel`

役割は, いま講義で映っているものを見失わないこと.

表示順

1. 現在の投影資料スナップショット
2. 現在の板書スナップショット
3. OCR抽出テキスト(更新時刻つき)
4. サムネイル履歴(直近10件)

仕様

- 更新単位は `source frame`
- `投影資料` と `板書` はタブで切替, 2カメラある場合は同時表示も可
- 画像クリックで拡大モーダル
- OCRテキストは元画像の時刻とリンク
- OCR領域ハイライトは任意, 初版は矩形overlayで可

#### 中央ペイン, `TranscriptPanel`

役割は, 字幕と翻訳を読みやすく出すこと.
このペインは常に見える.

1行コンポーネント仕様

```ts
type TranscriptLine = {
  id: string
  tsStartMs: number
  tsEndMs: number
  speakerLabel?: string
  sourceLangText: string
  translatedText?: string
  confidence?: number
  isPartial: boolean
  sourceRefs: {
    audioSegmentId: string
    sourceFrameIds?: string[]
  }
}
```

表示ルール

- 行頭に時刻
- 話者ラベル(取れた時だけ)
- 原文を上段, 翻訳を下段
- 部分字幕 isPartial は薄色, 確定で通常色
- 自動スクロールON/OFFを持つ
- ユーザーがスクロールしたら自動スクロールOFF
- `現在位置に戻る` ボタンを右下固定表示

字幕設定(クイック)

- 原文表示 ON/OFF
- 翻訳表示 ON/OFF
- 字幕サイズ
- 行間
- 背景濃度
- 表示言語

#### 右ペイン, `AssistPanel`

役割は, 講義中に最小限の補助を出すこと.
講義中に長文チャットをさせない.

表示ブロック

1. 講義状態
   - 録音
   - 文字起こし
   - 翻訳
   - 資料OCR
   - 接続状態
2. いまの要点(3件まで)
   - 30-60秒ごとに更新
3. 用語サポート
   - 専門用語
   - 短い説明
   - 翻訳語
4. 質問候補チップ
   - `この式の意味`
   - `もう一度説明して`
   - `この単語を日本語で`
5. ミニ質問入力(任意)
   - 講義中は短文のみ
   - 回答は右ペイン内で短く返す
   - 本格QAは review へ誘導

### モバイル代替レイアウト

- TopBarを2段に分ける
- `字幕 / 資料 / 補助` をセグメント切替
- 字幕を優先表示
- 画面下部に固定操作バー
  - 言語
  - 文字サイズ
  - 現在位置に戻る

### ライブ画面のイベントと状態

```ts
type LiveUiState = {
  connection: "connecting" | "live" | "reconnecting" | "degraded" | "error"
  transcriptLagMs: number
  translationLagMs: number
  sourceLagMs: number
  autoScroll: boolean
  selectedLanguage: "ja" | "en"
  transcriptDensity: "comfortable" | "compact"
  leftPanelMode: "slides" | "board" | "split"
}
```

### 性能目標(フロント側体感)

- 文字入力応答: 100ms以内
- パネル切替: 150ms以内
- 字幕行の追加描画: 1フレームで詰まらない
- スクロール中のレイアウトシフト: 0
- ライブイベント受信中のCPUスパイクを抑える(TranscriptはVirtualize)

---

## 8.4 `/lectures/:id/review` 講義後レビュー(根拠付きQA)

### 目的

講義後に, 発言と資料を根拠に自然に質問できるようにする.
審査では `講義中の蓄積が講義後価値に変わる` と見せる画面.

### レイアウト(デスクトップ)

- 左 30%: セッション概要
  - 講義情報
  - 生成要約
  - 主要トピック
  - ブックマーク
- 中央 40%: QAスレッド
  - 入力
  - 回答ストリーム
  - 根拠チップ
- 右 30%: ソースビューア
  - 発言原文
  - 時刻
  - 対応スナップショット
  - OCRテキスト

### QA入力仕様

```ts
type QaInput = {
  question: string
  answerLanguage: "ja" | "en"
  answerStyle: "short" | "normal" | "detailed"
  scope: "whole_lecture" | "current_topic" | "selected_range"
  selectedRange?: { fromMs: number; toMs: number }
}
```

### QA回答仕様(フロント表示)

```ts
type QaAnswerView = {
  answerId: string
  status: "streaming" | "done" | "error"
  markdown: string
  citations: Array<{
    citationId: string
    type: "audio" | "slide" | "board" | "ocr"
    label: string
    tsStartMs?: number
    tsEndMs?: number
    sourceFrameId?: string
  }>
  followups: string[]
}
```

表示ルール

- 回答はストリーミング表示
- 途中で止まっても, `再開` と `再生成` を出す
- 根拠チップを押すと右ペインがそのソースに同期
- 根拠が無い文は表示しない. 少なくとも1つの根拠を必須にする
- `この回答を引用付きで保存` ボタンを付ける(任意)

### review画面のデモ映えポイント

- 根拠チップ押下時に, 右ペインの該当発言と画像が同時にハイライト
- 長文回答でも, 見出しと根拠が先に見える
- `講義を見直す` で live相当のタイムライン位置へジャンプできる(録画再生が無くても時刻ジャンプUIだけ先に作れる)

---

## 8.5 `/lectures/:id/sources` ソース一覧

### 目的

OCRと文字起こしの元データを確認できる画面.
審査で `AIの説明責任` を示す.

### 表示

- 上部フィルタ
  - 種別(audio/slide/board/ocr)
  - 時間範囲
  - キーワード
- テーブル
  - 時刻
  - 種別
  - 抜粋
  - 信頼度(任意)
  - `開く` ボタン
- 右サイドプレビュー(任意)

### 仕様

- 検索0件はempty state
- table自体を残さずempty stateに置換
- 行クリックと `Enter` で開ける
- キーボード操作で完結可能

---

## 8.6 `/settings` 設定

### 設定カテゴリ

1. 表示
   - テーマ(light/dark/high-contrast)
   - 文字サイズ
   - 行間
   - 字幕背景
2. 言語
   - UI言語
   - 翻訳先言語
   - 原文/翻訳の表示優先
3. アクセシビリティ
   - アニメーションを減らす
   - キーボードショートカット表示
   - ライブ通知の読み上げ頻度
   - 色弱向け強調(任意)
4. 講義補助
   - 自動スクロール
   - 専門用語の補助表示
   - 質問候補チップ

### 実装

- 初版は右サイドシート
- URL同期不要
- LocalStorage保存 + サーバー同期(settings API)

---

## 8.7 `/operator/session` デモ運営画面(権限限定)

### 目的

本番用ではなく, コンペのデモ安定化用.
講義入力をわかりやすく見せる.

### 表示

- 音声入力状態
- スライドカメラ入力状態
- 板書カメラ入力状態
- 最新処理時刻
- 手動で `デモデータ再送` ボタン(任意)
- `観客向け画面を開く` ボタン

この画面は審査員に見せなくてもよい.
運営の手元だけで使う.

---

## 9. コンポーネント仕様

## 9.1 共通ルール

- すべての対話要素は keyboard focus 可
- hover依存の情報は, clickでも開ける
- クリック可能な要素は `cursor: pointer`
- アイコンボタンには必ず `aria-label`
- disabled時は見た目だけでなく操作不能にする

## 9.2 必須コンポーネント一覧

### AppShell

責務

- TopBar
- 左ナビ(必要な画面のみ)
- メイン領域
- トースト領域
- live region領域(視覚非表示)

Props

```ts
type AppShellProps = {
  children: React.ReactNode
  topbar?: React.ReactNode
  sidebar?: React.ReactNode
  rightRail?: React.ReactNode
}
```

### TopBar

要件

- 1行に収まらない時は段落ちしてよい
- 操作密度は高いが, touch targetは確保
- 接続状態pillは常時表示

### SegmentedControl

用途

- 字幕/資料/補助の切替
- 原文/翻訳表示切替

要件

- tablistと混同しない
- 押した瞬間に状態反映
- すべての項目に明確なラベル

### Tabs

用途

- `投影資料 / 板書`
- `要点 / 用語 / 状態`

要件

- WAI-ARIAの `tab`, `tablist`, `tabpanel` に準拠
- Arrowキーで移動
- `Enter`/`Space` で有効化(自動活性でも可, 初版は自動活性推奨)

### TranscriptList

要件

- Virtualized list
- 下方向追加
- isPartial行の差分更新を許可
- 行ごとに `sourceRefs` 保持
- 時刻クリックでreviewの該当位置へ遷移可能

### SourceFrameCard

要件

- 種別バッジ(slide/board)
- 取得時刻
- サムネイル
- OCR抜粋
- `拡大`
- `この時点へ移動`

### EmptyState

Variants

- no-data
- no-results
- error
- permission

要件

- 親コンテンツの空領域に置換して表示
- タイトル1行, 説明1-2行, CTA 1個
- 画像は任意, 無くても成立する

### Skeleton

Variants

- card
- table-row
- transcript-line
- source-card

要件

- 2-4秒以内に消える前提
- ボタンそのものには使わない
- reduced motion時は shimmerを止める

### Toast / InlineMessage

用途

- 保存完了
- 再接続開始
- 再接続成功
- エラー通知

要件

- 重要エラーは live region通知も同時に出す
- 自動消滅と手動クローズの両方対応
- 連続発火をまとめる

### Modal / SideSheet

用途

- ソース画像拡大
- 設定
- 確認ダイアログ

要件

- 開いたら最初の操作要素へfocus
- 閉じたら呼び出し元へfocus返却
- ESCで閉じる
- background scroll lock

---

## 10. アクセシビリティ仕様(必須)

## 10.1 基本

- WCAG 2.2 AA を最低ラインにする
- キーボードのみで主要導線を完了できる
- スクリーンリーダーで状態変化が追える
- 色だけで状態を伝えない
- 日本語, 英語で同等の情報量を出す

## 10.2 サイズと余白

- クリック対象は最低 24x24 CSS px, 推奨 40x40 以上
- 密なTopBarでも hit area を確保
- 文字の周りに余白を取り, 誤タップを防ぐ

## 10.3 コントラスト

- 通常テキスト 4.5:1 以上
- 大きい文字 3:1 以上
- UI部品の境界線やfocus ringも 3:1 以上

## 10.4 focus表示

- custom focus ringを実装
- ring幅は最低2px相当
- `outline: none` 単体は禁止
- destructive操作後, focusを消さない
- 非同期追加後もfocusの飛び先を固定する

推奨CSS

```css
.focus-ring {
  outline: 2px solid rgb(var(--focus));
  outline-offset: 2px;
}
```

## 10.5 live region(講義支援アプリ向けに重要)

視覚だけではなく読み上げで通知する.
専用の `sr-only` 領域を AppShell に1つ置く.

通知対象

- `接続中`
- `再接続中`
- `字幕を受信中`
- `QA回答を生成中`
- `QAでエラーが発生`
- `保存完了`

ルール

- loading中の連続通知は5秒間隔以下にしない
- 完了したら loading通知を止める
- エラーは視覚表示と同じ文面を読み上げる

## 10.6 モーション

- OSの reduced motion を尊重
- shimmer, parallax, 大きな移動を止める
- 状態変化は文言でも伝える

## 10.7 字幕と可読性

- 字幕の背景濃度を変更可能
- 行間調整を提供
- 長文は1行が長くなりすぎない幅に制限
- 日本語字幕は禁則を簡易に考慮し, 記号前で極端に改行しない

---

## 11. 多言語UI仕様

## 11.1 対応言語(初版)

- 日本語
- 英語

将来拡張前提でキー設計する.
文字列ハードコード禁止.

## 11.2 i18n実装ルール

- `locales/ja/*.json`, `locales/en/*.json`
- 文言キーは画面単位
  - `live.topbar.connection.live`
  - `review.qa.retry`
- エラー文言もi18n対象
- 日時は `Intl.DateTimeFormat`
- 数字は `Intl.NumberFormat`

## 11.3 翻訳表示のUIルール

- 原文と翻訳の上下順は設定で切替可
- どちらか片方だけ表示可能
- 講義言語とUI言語は別設定
- 日本語UIでも英語訳字幕を出せる

---

## 12. 状態管理とデータフロー

## 12.1 状態の分割

- サーバー同期データ: TanStack Query
- ライブストリーム一時状態: Zustand
- フォーム状態: react-hook-form
- ユーザー設定: LocalStorage + Zustand

## 12.2 WebSocketイベント(想定)

```ts
type WsEvent =
  | { type: "session.status"; payload: SessionStatusPayload }
  | { type: "transcript.partial"; payload: TranscriptLine }
  | { type: "transcript.final"; payload: TranscriptLine }
  | { type: "translation.final"; payload: { lineId: string; translatedText: string } }
  | { type: "source.frame"; payload: SourceFrame }
  | { type: "source.ocr"; payload: SourceOcrChunk }
  | { type: "assist.summary"; payload: AssistSummaryPayload }
  | { type: "assist.term"; payload: AssistTermPayload[] }
  | { type: "qa.answer.chunk"; payload: QaAnswerChunk }
  | { type: "qa.answer.done"; payload: QaAnswerDone }
  | { type: "error"; payload: UiErrorPayload }
```

## 12.3 再接続

- 1回目 1秒
- 2回目 2秒
- 3回目 5秒
- 以降 10秒固定
- `reconnecting` 状態をUIに出す
- 復帰後, `復帰しました` をトースト + live region

## 12.4 ローカル保持

保存対象

- UI言語
- 翻訳表示言語
- 字幕サイズ
- 行間
- テーマ
- reduced motion上書き設定
- 自動スクロールON/OFF

---

## 13. API契約(フロントが前提とする最低条件)

バックエンド仕様とは別文書で管理してよいが, フロント実装を止めないために前提をここで固定する.

### 13.1 RESTエンドポイント(最低)

```text
GET    /api/v4/health
POST   /api/v4/course/readiness/check
POST   /api/v4/lecture/session/start
POST   /api/v4/lecture/session/finalize
GET    /api/v4/settings/me
POST   /api/v4/settings/me
```

### 13.2 必須ヘッダ

- `X-Lecture-Token` (default: `dev-lecture-token`)
- `X-User-Id` (default: `demo-user`)

### 13.3 ストリーミング

どちらか一方でよい.

- WebSocket
- Server-Sent Events(フォールバック)

### 13.4 時刻とID

- 時刻は ISO 8601 + UTC
- 画面表示時にローカル時刻へ変換
- すべてのソース要素に stable id を付与
- QA引用の citationId は回答再生成後も衝突しない

---

## 14. デモ演出仕様(審査向け)

派手さより, `理解できる`, `信頼できる`, `使えそう` の順で見せる.

## 14.1 画面演出の順序

1. 講義一覧から liveへ入る
2. 字幕と翻訳が流れる
3. 板書/投影資料が更新される
4. 用語補助が出る
5. 講義終了後に reviewへ移る
6. QAして, 根拠チップで元発言と資料に飛ぶ

この順序で迷わないUIを作る.
1画面に詰め込みすぎない.

## 14.2 見た目で効くポイント

- TopBarの状態pillを小さく常設
- 中央字幕を主役にして, 周辺情報をカードで整理
- カードの角丸と余白を揃える
- skeletonとempty stateを最初から入れる
- loading, success, errorの見た目を統一する

## 14.3 失敗時デモの保険

- 接続断を再現しても `再接続中` が見える
- source更新が止まっても, 最終更新時刻を表示
- QA失敗時は, リトライ導線と理由を出す
- 空データでもempty stateで破綻しない

---

## 15. 監視と計測(フロント)

Azure Application Insights で最低限これを送る.

## 15.1 主要イベント

- `page_view`
- `lecture_enter_live`
- `caption_settings_changed`
- `source_frame_opened`
- `qa_submitted`
- `qa_answer_completed`
- `qa_answer_failed`
- `reconnect_started`
- `reconnect_succeeded`

## 15.2 主要メトリクス

- live画面初回表示までの時間
- 字幕初回表示までの時間
- QA回答開始までの時間
- QA回答完了までの時間
- 再接続回数
- フロントエラー数

個人情報や講義本文は送らない.
送るのはID, 区間, サイズ, 成功/失敗のメタ情報だけ.

---

## 16. 実装フォルダ構成(推奨)

```text
src/
  app/
    router.tsx
    providers.tsx
    app-shell.tsx
  pages/
    landing/
    lectures/
    lecture-live/
    lecture-review/
    lecture-sources/
    settings/
    operator-session/
  features/
    transcript/
      components/
      stores/
      hooks/
      types.ts
    sources/
    assist/
    qa/
    preferences/
  components/
    ui/              # shadcn base wrappers
    common/          # AppShell, EmptyState, Skeleton, ErrorBoundary
    feedback/        # Toast, InlineMessage, LiveStatusPill
  lib/
    api/
    ws/
    i18n/
    analytics/
    a11y/
    utils/
  styles/
    globals.css
    tokens.css
  locales/
    ja/
    en/
```

---

## 17. 受け入れ条件(Definition of Done)

## 17.1 機能

- live画面で字幕, 翻訳, source, 状態表示が同時に見える
- review画面で根拠付きQAが動く
- settingsで表示設定が変わる
- 日本語UI, 英語UIを切り替えられる
- 日本語学生も日本語UIでそのまま使える

## 17.2 アクセシビリティ

- キーボードだけで `講義一覧 -> live -> review -> QA送信` ができる
- focus ringが常に見える
- 主要トーストとQA状態がlive regionで通知される
- 文字サイズ拡大でレイアウトが壊れにくい
- reduced motionで過剰な動きが止まる

## 17.3 見た目

- light/dark/high-contrast が切替できる
- spacing, 角丸, 影が統一されている
- empty/loading/errorの状態が未実装のまま残っていない
- デモ中にレイアウト崩れが起きない

---

## 18. 実装の着手順(AI-Agent向け)

AI-Agentはこの順に作ると手戻りが少ない.

1. トークン, テーマ, AppShell を作る
2. ルーティングとページ雛形を作る
3. 共通コンポーネント(EmptyState, Skeleton, Toast, SideSheet)を作る
4. live画面の固定レイアウトを作る
5. TranscriptList をVirtualizedで作る
6. SourcePanel と AssistPanel を作る
7. review画面のQAレイアウトと根拠チップ連動を作る
8. 設定画面とLocalStorage保存を作る
9. WebSocket接続と再接続表示をつなぐ
10. a11y調整(focus, live region, keyboard)
11. reduced motion, high-contrast, 例外状態を詰める
12. Application Insights を入れる

---

## 19. 参考にした先行例の反映メモ

- Microsoft Fluent 2 の spacing, token, typography, motion, shape の考え方を採用
- GitHub Primer の AI UI向けアクセシビリティ実践(loading通知, focus管理)を採用
- IBM Carbon の empty state / loading state パターンを採用
- W3C WCAG 2.2 と WAI-ARIA APG をアクセシビリティ基準として採用
- Apple HIG の hierarchy, consistency, accessibility の原則をUI全体の判断基準に採用

以上.
