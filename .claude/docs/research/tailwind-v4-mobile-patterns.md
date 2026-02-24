# Tailwind CSS v4 Mobile Patterns

## Summary
Tailwind CSS v4.2.0のモバイルファーストパターンと、SIT-Copilotプロジェクトでの適用方法についてまとめました。

## Tailwind CSS v4 Key Features

### 1. @theme Directive
```css
@theme {
  /* カスタムブレークポイント定義 */
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
}
```

### 2. Default Breakpoints
| Prefix | Min Width | Target Devices |
|--------|-----------|----------------|
| (none) | 0px | Mobile first (base) |
| sm: | 640px | Large tablets, small laptops |
| md: | 768px | Small laptops, tablets |
| lg: | 1024px | Desktops |
| xl: | 1280px | Large desktops |
| 2xl: | 1536px | Extra large screens |

### 3. Mobile-First Utility Pattern
```html
<!-- モバイルでは縦積み、md以上で横並び -->
<div class="flex flex-col md:flex-row">
  ...
</div>

<!-- モバイルでは小さい文字、lg以上で大きく -->
<h1 class="text-lg lg:text-xl">
  ...
</h1>
```

## Component Patterns

### Container Pattern
```html
<!-- モバイル全幅、デスクトップでmax-width制限 -->
<div class="w-full md:max-w-2xl lg:max-w-4xl">
  ...
</div>
```

### Grid Pattern
```html
<!-- モバイル1列、タブレット2列、デスクトップ3列 -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  ...
</div>
```

### Navigation Pattern
```html
<!-- モバイルで非表示、md以上で表示 -->
<nav class="hidden md:flex">
  ...
</nav>

<!-- モバイルで表示、md以上で非表示 -->
<button class="flex md:hidden">
  <!-- Hamburger icon -->
</button>
```

### Spacing Pattern
```html
<!-- モバイル狭め、デスクトップ広め -->
<div class="p-4 md:p-6 lg:p-8">
  ...
</div>
```

## Current Implementation in SIT-Copilot

### Positive Findings
1. **index.css**: `@theme` ディレクティブでデザイントークン定義済み
2. **グローバルスタイル**: `.btn` でタッチターゲット対応済み（40x40px）
3. **アクセシビリティ**: `focus-visible` スタイル定義済み

### Gap Analysis

#### AppShell (/home/argo/sit-copilot/frontend/src/components/common/AppShell.tsx)
- **現在**: sidebar/rightRailが固定幅（w-64, w-80）
- **課題**: モバイルでオーバーレイ表示に切り替える必要
- **推奨**: `hidden md:block` でモバイル非表示、ハンバーガーメニューで開閉

#### Modal (/home/argo/sit-copilot/frontend/src/components/ui/Modal.tsx)
- **現在**: 中央モーダルのみ
- **課題**: モバイルでBottom Sheet対応が必要
- **推奨**: `bottomSheet` prop追加、`fixed bottom-0` スタイル

#### TopBar (/home/argo/sit-copilot/frontend/src/components/ui/TopBar.tsx)
- **現在**: レスポンシブ対応なし
- **課題**: モバイルでタイトルとアクションの縮小・折りたたみが必要

#### LandingPage (/home/argo/sit-copilot/frontend/src/pages/landing/LandingPage.tsx)
- **現在**: `lg:grid-cols-5` で2カラムレイアウト
- **良い実装**: `md:text-5xl` でフォントサイズレスポンシブ対応済み

## Recommendations

### 1. Add Mobile Breakpoint to @theme
```css
@theme {
  /* 既存のブレークポイントに加え、モバイル対応を明確化 */
  --breakpoint-xs: 375px; /* Small mobile phones */
}
```

### 2. Create Mobile-First Utility Classes
```css
/* モバイルで非表示、sm以上で表示 */
.hidden-mobile {
  @apply hidden sm:block;
}

/* モバイルのみ表示 */
.mobile-only {
  @apply block sm:hidden;
}
```

### 3. Bottom Sheet Component
```tsx
// 新規コンポーネント提案
interface BottomSheetProps {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
}
```

### 4. Hamburger Menu Component
```tsx
// 新規コンポーネント提案
interface HamburgerMenuProps {
  items: MenuItem[];
  isOpen: boolean;
  onToggle: () => void;
}
```

## Sources
- Tailwind CSS v4 Documentation (https://tailwindcss.com)
- Tailwind CSS v4 Release Notes
- Mobile-First Design with Tailwind CSS
