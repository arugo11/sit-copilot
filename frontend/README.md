# SIT Copilot Frontend

ログイン不要のデモUIです。  
`X-Lecture-Token` / `X-Procedure-Token` と `X-User-Id` をヘッダに付与して FastAPI (`/api/v4/*`) を呼びます。

デモ進行台本は [../docs/DEMO_RUNBOOK.md](../docs/DEMO_RUNBOOK.md) を参照してください。

## セットアップ

```bash
cd frontend
npm install
```

## 環境変数

`frontend/.env` に必要に応じて設定します。

```bash
# 開発時は未設定なら同一オリジン(/api) + Vite proxyを使用
# 別オリジンAPIへ直接接続したい場合のみ設定
VITE_API_BASE_URL=http://localhost:8000
VITE_LECTURE_API_TOKEN=dev-lecture-token
VITE_PROCEDURE_API_TOKEN=dev-procedure-token
VITE_DEMO_USER_ID=demo-user
```

- `VITE_API_BASE_URL`: APIベースURL（未設定時: devは`/api`経由、build環境は`http://localhost:8000`）
- `VITE_LECTURE_API_TOKEN`: `X-Lecture-Token` の値
- `VITE_PROCEDURE_API_TOKEN`: `X-Procedure-Token` の値
- `VITE_DEMO_USER_ID`: `X-User-Id` の値

## 開発起動

1. バックエンド起動（リポジトリルート）

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

2. フロント起動（別ターミナル）

```bash
cd frontend
npm run dev
```

## ビルド

```bash
cd frontend
npm run build
```

- 公開環境の `X-Lecture-Token` / `X-Procedure-Token` / `X-User-Id` は
  runtime ではなく build-time に `VITE_*` として埋め込みます。
- token をローテーションした場合は backend secret 更新後に
  frontend を再ビルドし、Static Web Apps を再デプロイしてください。
- 講義ライブの字幕イベント時刻は epoch milliseconds です。backend が
  PostgreSQL の場合、対応する時刻列は `BIGINT` である必要があります。

## 実API確認（curl）

### readiness

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v4/course/readiness/check" \
  -H "Content-Type: application/json" \
  -H "X-Lecture-Token: dev-lecture-token" \
  -d '{"course_name":"デモ講義","syllabus_text":"評価は課題と発表です。","lang_mode":"ja"}'
```

### settings read

```bash
curl -sS "http://127.0.0.1:8000/api/v4/settings/me" \
  -H "X-Lecture-Token: dev-lecture-token" \
  -H "X-User-Id: demo-user"
```

### settings write

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v4/settings/me" \
  -H "Content-Type: application/json" \
  -H "X-Lecture-Token: dev-lecture-token" \
  -H "X-User-Id: demo-user" \
  -d '{"settings":{"theme":"light","language":"ja"}}'
```
