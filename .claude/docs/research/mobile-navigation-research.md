# Mobile Navigation Research (2025)

## Summary
教育/講義プラットフォームにおけるモバイルナビゲーションパターンの調査結果。Apple HIG、Google Material Design、業界ベストプラクティスに基づき、SIT-Copilotアプリケーションに最適なパターンを推奨。

## Navigation Structure Analysis

### Current Application Pages
1. **Landing** - 説明・クイックスタート（エントリーポイント）
2. **Lectures** - セッション一覧（講義一覧）
3. **Lecture Live** - ライブ講義視聴（メイン機能）
4. **Lecture Sources** - 講義資料（ソースパネル）
5. **Review** - セッション復習・QA（復習機能）
6. **Settings** - 設定（ユーザー設定）
7. **Procedure** - 手続き（オンボーディング）
8. **Readiness** - 準備確認（チェックリスト）

### User Flow Priority
1. **Primary**: Lecture Live（メイン機能）
2. **Secondary**: Lectures（一覧）、Review（復習）
3. **Tertiary**: Settings（設定）、Landing（説明）

## Design Guidelines Comparison

### Apple Human Interface Guidelines (HIG)

#### Bottom Navigation (Tab Bar)
- **Max items**: 5推奨（Scrollable Tab Barは例外的）
- **Icon + Label**: 必須（アイコンのみは非推奨）
- **Touch target**: 44x44pt minimum
- **Behavior**: タップで即座に切り替え（ハイライト状態維持）

#### Navigation Patterns for Content Apps
- **Tab Bar**: トップレベルのカテゴリー（3-5項目）
- **Sidebar**: 階層構造、多くの項目
- **Modal/Sheet**: 一時的な設定やオプション

### Google Material Design 3

#### Navigation Bar (Bottom)
- **Max items**: 5推奨（4が理想）
- **Icon + Label**: 推奨（ラベルは省略可能だが推奨）
- **Touch target**: 48x48dp minimum
- **Behavior**: タップで即座に切り替え

#### Navigation Drawer
- **用途**: 多くのナビゲーション項目（6+）
- **タイプ**: 
  - Standard drawer（モーダル、オーバーレイ）
  - Permanent drawer（デスクトップのみ）

## Recommended Pattern for SIT-Copilot

### Hybrid Pattern: Bottom Nav + Drawer

#### Bottom Navigation (Primary Tabs)
**3-4項目のみ配置**

| Position | Destination | Icon | Rationale |
|----------|-------------|------|-----------|
| 1 | Lectures | リストアイコン | セッション一覧、エントリーポイント |
| 2 | Live | ライブアイコン | メイン機能 |
| 3 | Review | 復習アイコン | セッション復習 |

**設計判断**:
- 3項目はiOS/Android両方のガイドラインに準拠
- 頻繁に行き来するトップレベル画面のみ
- Settingsは使用頻度低いためDrawerへ

#### Drawer Menu (Hamburger)
**6+項目配置**

| Section | Items |
|---------|-------|
| **Primary** | （Bottom Navと重複なし） |
| **Secondary** | Sources, Procedure, Readiness |
| **Settings** | Settings, Language, Theme |

**設計判断**:
- 低頻度機能をDrawerに配置
- オンボーディング系は初期のみ使用

## Implementation Details

### Bottom Navigation Component

#### Layout
```tsx
// 構造案
<div className="fixed bottom-0 left-0 right-0 bg-bg-surface border-t border-border md:hidden">
  <nav className="flex justify-around items-center h-16">
    {/* 3つのナビゲーションアイテム */}
  </nav>
</div>
```

#### Touch Target Size
```css
/* WCAG 2.1 AAA: 44x44px minimum */
.nav-item {
  min-height: 44px;
  min-width: 44px;
  padding: 8px 12px;
}
```

#### Icon + Label
```tsx
<button className="flex flex-col items-center gap-1">
  <Icon className="w-6 h-6" />
  <span className="text-xs">{label}</span>
</button>
```

### Drawer (Hamburger Menu) Component

#### Layout
```tsx
// モバイル: Overlay drawer
// デスクトップ: Persistent sidebar
<div className="fixed inset-y-0 left-0 z-50 w-64 bg-bg-surface md:relative md:block">
  {/* Drawer content */}
</div>
```

#### Animation
```css
/* スライドインアニメーション */
@media (prefers-reduced-motion: no-preference) {
  .drawer {
    transition: transform 240ms var(--ease-standard);
  }
  .drawer.closed {
    transform: translateX(-100%);
  }
}
```

## Accessibility Requirements

### 1. Touch Target Size
- **Minimum**: 44x44px（WCAG 2.1 AAA）
- **Recommended**: 48x48px（Material Design 3）

### 2. Screen Reader Support
```tsx
/* ARIA attributes */
<nav aria-label="Primary navigation">
  <button
    aria-current={isActive ? 'page' : undefined}
    aria-label="Lectures"
  >
    ...
  </button>
</nav>
```

### 3. Keyboard Navigation
- Tab: 順次フォーカス移動
- Arrow keys: Bottom Nav内で左右移動
- ESC: Drawerを閉じる

### 4. Focus Management
- Drawerオープン時: 最初の項目にフォーカス
- Drawerクローズ時: トリガーボタンにフォーカス復帰
- Focus trap: Drawer内でループ

### 5. Live Region Announcements
```tsx
/* ページ切り替えを通知 */
<div aria-live="polite" aria-atomic="true">
  Now viewing: Lectures
</div>
```

## Anti-Patterns to Avoid

### ❌ Bottom Nav with 5+ Items
- 問題: アイコンが小さくなり、タッチターゲットが縮小
- 解決: 4項目以内に抑え、残りはDrawerへ

### ❌ Icon-Only Bottom Nav
- 問題: アイコンだけでは意味が不明確
- 解決: Icon + Label（iOS/Android両方推奨）

### ❌ "More" Menu in Bottom Nav
- 問題: 余計なタップ、UX悪化
- 解決: 低頻度項目は最初からDrawerへ

### ❌ Sidebar + Bottom Nav 同時表示
- 問題: 画面スペース圧迫、混乱
- 解決: レスポンシブ切替（モバイル=Bottom Nav、デスクトップ=Sidebar）

### ❌ Hiding Bottom Nav on Scroll
- 問題: アクセシビリティ低下、目的のナビゲーションが見つからない
- 解決: 常時表示（auto-hideは非推奨）

## Responsive Strategy

### Mobile (< 768px)
```
┌─────────────────────────────┐
│ Top Bar        [≡]          │
├─────────────────────────────┤
│                             │
│      Main Content           │
│                             │
├─────────────────────────────┤
│ [Lectures] [Live] [Review]  │  ← Bottom Nav
└─────────────────────────────┘
```

### Tablet (768px - 1024px)
```
┌─────────────────────────────────────┐
│ Top Bar                             │
├──────┬──────────────────────────────┤
│      │                              │
│ Side │      Main Content            │
│ bar  │                              │
│      │                              │
└──────┴──────────────────────────────┘
```

### Desktop (1024px+)
```
┌──────────────────────────────────────────┐
│ Top Bar                                  │
├──────┬─────────────────┬─────────────────┤
│      │                 │                 │
│ Side │   Main Content  │   Right Rail    │
│ bar  │                 │   (Assist)      │
│      │                 │                 │
└──────┴─────────────────┴─────────────────┘
```

## Page-to-Component Mapping

### Bottom Nav Items
- **Lectures** → `/lectures`
- **Live** → `/lectures/:id/live`
- **Review** → `/lectures/:id/review`

### Drawer Items
- **Sources** → `/lectures/:id/sources`
- **Procedure** → `/procedure`
- **Readiness** → `/readiness`
- **Settings** → `/settings`

### Not in Nav (Linked internally)
- **Landing** → `/` （初期アクセスのみ、ログイン後は非表示）

## Recommendations Summary

1. **Bottom Nav**: 3項目（Lectures, Live, Review）
2. **Drawer**: 4項目（Sources, Procedure, Readiness, Settings）
3. **Touch Target**: 44x44px minimum
4. **Icon + Label**: 必須
5. **Responsive切替**: 
   - モバイル: Bottom Nav + Drawer
   - タブレット以上: Sidebar + Right Rail

## Sources
- Apple Human Interface Guidelines: Bars and Navigation
- Google Material Design 3: Navigation Component
- WCAG 2.1: Success Criterion 2.5.5 (Target Size)
- Nielsen Norman Group: Mobile Navigation Usability
