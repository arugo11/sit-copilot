# Responsive Design Best Practices (2025)

## Summary
モバイルファーストのレスポンシブデザインに関する2025年のベストプラクティスを調査・まとめました。

## Key Findings

### 1. Mobile-First Approach
- **基本原則**: 最小画面（320px-375px）から設計を開始
- **プログレッシブエンハンスメント**: 大きな画面で機能追加
- **パフォーマンス優先**: モバイルで最適化することでデスクトップも高速化

### 2. WCAG 2.1 / 2.2 Touch Target Requirements
- **AAA基準（WCAG 2.1）**: タッチターゲット最低44x44px
- **AA基準（WCAG 2.2）**: タッチターゲット最低24x24px
- **間隔要件**: ターゲット間に24x24pxの余白（ターゲットが小さい場合）
- **適用範囲**: タッチ操作、マウスクリック、キーボード操作

### 3. Fluid Typography with clamp()
```css
/* 基本構文: clamp(最小値, 推奨値, 最大値) */
font-size: clamp(1.5rem, 2.5vw + 1rem, 3rem);
```

- **メリット**: メディアクエリ不要、スムーズなスケーリング
- **ブラウザサポート**: 最新ブラウザで広くサポート

### 4. Mobile Navigation Patterns
- **ハンバーガーメニュー**: 3本線アイコンでメニューを隠蔽
- **ボトムナビゲーション**: モバイルで親指が届きやすい位置
- **ドロワーメニュー**: 画面端からスライドイン
- **スタックナビゲーション**: 垂直方向にメニューアイテムを展開

### 5. Component-Specific Patterns

#### Modal/Dialog
- **モバイル**: Bottom sheet（画面下からスライドアップ）
- **デスクトップ**: Center modal（画面中央）

#### Sidebar/Panel
- **モバイル**: Off-canvas drawer（オーバーレイ表示）
- **デスクトップ**: Persistent sidebar（常時表示）

#### Cards/Lists
- **モバイル**: Single column（1列）
- **タブレット**: 2 columns
- **デスクトップ**: 3 columns+

#### Forms
- **モバイル**: Full-width inputs、ラジオボタンを縦積み
- **デスクトップ**: 適切な幅、横並び配置

## Recommendations

### For SIT-Copilot Project

1. **現在の状況**:
   - Tailwind CSS v4.2.0（最新版）を使用
   - `@theme` ディレクティブでテーマ定義済み
   - 基本的なレスポンシブクラス（md:, lg:, xl:）は使用されている
   - **課題**: モバイル（320px-640px）での最適化が不十分

2. **優先実装項目**:
   - [ ] AppShellのモバイル対応（sidebar/off-canvasの切替）
   - [ ] ModalのBottom sheet対応（モバイル）
   - [ ] ボタン・タッチターゲットの最小サイズ確保（44x44px）
   - [ ] フォントサイズのfluid typography対応
   - [ ] TopBarのモバイル対応（ハンバーガーメニュー）

3. **既存の良い実装**:
   - `.btn` クラスで `min-height: 40px; min-width: 40px;` 定義済み
   - `skip-link` でキーボードユーザー配慮済み
   - `focus-visible` でアクセシビリティ対応済み

## Sources
- WCAG 2.1 Success Criterion 2.5.5 (Target Size)
- WCAG 2.2 Success Criterion 2.5.8 (Target Size - Minimum)
- CSS clamp() Function (MDN)
- Mobile-First Responsive Design (Smashing Magazine)
- Tailwind CSS v4 Documentation
