# SIT Copilot

SIT Copilot は、講義中の理解を支援することにフォーカスしたアプリです。現行実装では、セッション管理付きのライブ字幕表示、言語切り替え、要点/用語サポート、根拠付きミニ質問 QA、設定保存を中心に構成されています。

## 技術スタック

- Backend: FastAPI / Python
- Frontend: React + Vite + TypeScript

## 現在の実装に合わせた機能紹介

`frontend/src/app/router.tsx` の現行ルーティングに基づく機能です。

### 現在有効な導線

- `/`
  - ランディング画面。講義一覧 (`/lectures`) への導線を提供。
- `/lectures`
  - セッション開始、一覧表示、セッション終了、セッション削除。
  - セッション一覧はローカル保存 (`localStorage`) と同期。
- `/lectures/:id/live`
  - リアルタイム字幕表示。
  - 表示言語切り替え (`ja` / `easy-ja` / `en`)。
  - 翻訳フォールバック表示。
  - 要点サポート/用語サポート（トグルあり）。
  - 右ペインのミニ質問で根拠付き QA。
- `/settings`
  - テーマ、文字サイズ、字幕密度、自動スクロール、UI 言語、低モーション設定。
- `/lectures/:id/sources`
  - ソース一覧画面。現在はモックデータ表示。

### リダイレクト導線（現在は `/lectures` へ遷移）

- `/readiness-check`
- `/procedure`
- `/lectures/:id/qa`
- `/lecture/:session_id/qa`
- `/lectures/:id/review`

## ローカルでビルドする方法（Backend + Frontend）

### 前提条件

- Python 3.11+
- `uv`
- Node.js 20+
- `npm`

### 1. Backend の依存解決

```bash
uv sync --frozen --all-extras
```

### 2. Frontend の依存解決

```bash
npm ci --prefix frontend
```

### 3. 手動起動（スクリプト不使用）

ターミナルを2つ使って、以下をそれぞれ実行します。

ターミナルA（Backend）:

```bash
WEAVE_ENABLED=false uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

ターミナルB（Frontend）:

```bash
npm run dev --prefix frontend -- --host 127.0.0.1 --port 3000 --strictPort
```

開発時は Frontend (`127.0.0.1:3000`) の `/api` が Backend (`127.0.0.1:8000`) にプロキシされます。

### 4. 手動での動作確認

```bash
# Backend 直アクセス
curl -i http://127.0.0.1:8000/api/v4/health

# Frontend 経由のAPI疎通（proxy確認）
curl -i http://127.0.0.1:3000/api/v4/health
```

ブラウザでは `http://127.0.0.1:3000/` を開いて確認してください。

### 5. 停止方法（手動）

それぞれのターミナルで `Ctrl + C` を押して停止します。

### 6. `ERR_CONNECTION_REFUSED` のとき

```bash
# Backend が待ち受けているか
lsof -nP -iTCP:8000 -sTCP:LISTEN

# Frontend が待ち受けているか
lsof -nP -iTCP:3000 -sTCP:LISTEN
```

- `8000` が空なら Backend を再起動
- `3000` が空なら Frontend を再起動

## デプロイされている URL

- Frontend: `https://proud-sand-00bb37700.1.azurestaticapps.net/`

2026-02-23 時点の運用記録に基づいています。更新時は `/.claude/docs/DESIGN.md` を参照してください。

## 補足リンク

- 実装仕様: `docs/SPEC.md`
- フロント設計: `docs/frontend.md`
- デモ運用: `docs/DEMO_RUNBOOK.md`
