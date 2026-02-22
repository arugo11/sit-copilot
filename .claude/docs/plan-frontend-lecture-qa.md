## Implementation Plan: Frontend - Lecture QA Screen

### Purpose
講義後QA機能のフロントエンド画面を実装し、ユーザーが講義セッションに対して質問し、AI生成の回答と引用情報を表示できるようにする。

### Scope

**New Files:**
- `frontend/src/pages/lectures/LectureQAPage.tsx` - メインQAページ

**Modified Files:**
- `frontend/src/app/router.tsx` - ルーティング追加 `/lectures/:id/qa`

**Dependencies (All Already Implemented):**
- React Router v6
- Zustand (状態管理)
- TanStack React Query
- API client: `lib/api/client.ts`
- Store: `stores/reviewQaStore.ts`
- Mapper: `features/review/qaResponseMapper.ts`
- Components: `features/review/components/QAStreamBlocks.tsx`

### Implementation Steps

#### Step 1: 既存フロントエンド構造の調査 ✅ (COMPLETED)
- [x] `frontend/`ディレクトリ構造を確認
- [x] 既存のページコンポーネントパターンを確認（`LectureReviewPage.tsx`）
- [x] APIクライアントの実装パターンを確認（`lib/api/client.ts`）
- [x] Zustandストアの使用状況を確認（`reviewQaStore.ts`）
- [x] ルーティング設定を確認（`app/router.tsx`）

**Verification**: ✅ 既存コードベースのパターンを理解

**Key Findings:**
- `lectureQaApi` が既に実装済み（`buildIndex`, `ask`, `followup`）
- 型定義も完備（`LectureAskRequest/Response`, `LectureSource`, etc）
- `useReviewQaStore` (Zustand) を再利用可能
- `QAStreamBlocks` コンポーネントを再利用可能
- `LectureReviewPage` が参考実装

#### Step 2: ルーティングの追加
- [ ] `frontend/src/app/router.tsx` に `/lectures/:id/qa` ルートを追加
- [ ] `LectureQAPage` を lazy load

**Verification**: ルート追加後、TypeScriptエラーなし

#### Step 3: メインページの実装
- [ ] `frontend/src/pages/lectures/LectureQAPage.tsx` を作成
- [ ] `LectureReviewPage` をベースに簡素化
  - サイドバーなし（QAに集中）
  - ソースビューアーなし
  - シンプルなカードベースレイアウト
- [ ] `useReviewQaStore` をそのまま使用
- [ ] `requestReviewQaAnswer` をそのまま使用
- [ ] インデックス事前構築ロジック
- [ ] 質問送信→回答表示のフロー
- [ ] エラー表示（ソースなし、バックエンドエラー）

**Verification**: ページ全体でQAフローが完結すること

#### Step 4: スタイリングとUX改善
- [ ] レスポンシブデザイン対応
- [ ] ローディング表示（既存の badge ステータス）
- [ ] エラーメッセージの表示（日本語）
- [ ] アクセシビリティ（ARIAラベル等）

**Verification**: モバイル/デスクトップ両方で使用できること

#### Step 5: テストと修正
- [ ] 手動テスト：正常系（質問→回答）
- [ ] 手動テスト：異常系（ソースなし、ネットワークエラー）
- [ ] 手動テスト：フォローアップ質問
- [ ] TypeScript型チェック
- [ ] バグ修正

**Verification**: すべてのシナリオで期待通り動作すること

### Risks & Considerations

**技術的リスク:**
1. **Azure OpenAIレイテンシ**: 回答生成に数秒かかる可能性
   -対策: 既存のローディング表示（badge status）で対応
2. **インデックス未構築**: 初回アクセス時にインデックスがない状態
   -対策: `warmupReviewQaIndex` 関数で対応（既存実装）
3. **フォローアップ質問**: 会話履歴の管理
   -対策: `hasSuccessfulTurn` フラグで判定（既存実装）

**UI/UX:**
1. **回答品質のバリエーション**: confidenceスコアに応じた表示
   -対策: 必要に応じてバッジ表示を追加
2. **サイドバーなし**: Reviewページとの違い
   -対策: ユーザーには「簡易版QA」として案内

**依存関係:**
1. バックエンドAPIが正常に動作している必要あり
2. 講義セッションが存在している必要あり
3. `lecture_api_token` 環境変数の設定

### Implementation Details

**Page Structure:**
```tsx
<LectureQAPage>
  <AppShell topbar={...}>
    <QuestionInput form />
    <QAStreamBlocks turns={qaTurns} />
  </AppShell>
</LectureQAPage>
```

**API Flow:**
1. Mount → `warmupReviewQaIndex(sessionId)`
2. User submits question → `requestReviewQaAnswer()`
3. Response → `applyChunk()` → `applyDone()`
4. Display with `QAStreamBlocks`

**State Management:**
```tsx
const qaTurns = useReviewQaStore((state) => state.qaTurns)
const submitQuestion = useReviewQaStore((state) => state.submitQuestion)
// ... other store methods
```

**Error Handling (Japanese):**
- 401: "認証エラー - デモトークン設定を確認してください"
- 404: "セッションが見つかりません - 講義一覧へ戻ります"
- 503: "QAバックエンド利用不可 - 現在は回答生成サービスを利用できません"
- Other: "回答の取得に失敗しました"

### Open Questions (Answered)

1. **認証**: どのように`lecture_api_token`をヘッダーに含めるか？
   -✅ 既に `lib/api/client.ts` で自動設定済み

2. **エラー表示**: バックエンドエラーのユーザー向けメッセージ
   -✅ 既存の `LectureReviewPage` の日本語メッセージを流用

3. **インデックス構築**: バックグラウンドで構築中、ユーザーは操作可能にするか？
   -✅ `warmupReviewQaIndex` で非同期構築、ユーザー操作は可能

4. **引用の表示順序**: タイムスタンプ順か、関連性順か？
   -✅ APIが返す順序（タイムスタンプ順）をそのまま使用

5. **フォローアップ会話履歴**: ローカルのみか、永続化か？
   -✅ Zustandストアでローカル管理（既存実装）

### Success Criteria

- [ ] `/lectures/:id/qa`ページにアクセスできる
- [ ] 質問を入力し、回答を表示できる
- [ ] 回答に引用情報（タイムスタンプ、ソース）が含まれる
- [ ] フォローアップ質問ができる
- [ ] エラー状態（ソースなし、バックエンドエラー）が適切に表示される
- [ ] レスポンシブデザインでモバイルでも使用できる
- [ ] TypeScript型チェックが通る
- [ ] ruff format が通る

### Files Changed

**New:**
- `frontend/src/pages/lectures/LectureQAPage.tsx` (約200行)

**Modified:**
- `frontend/src/app/router.tsx` (+3 lines)

**Total Estimated:** 1 new file, 1 modified file, ~200 lines of code
