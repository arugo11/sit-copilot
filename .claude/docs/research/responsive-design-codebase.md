# Frontend Codebase Analysis: Responsive Design

## Executive Summary

This document provides a comprehensive analysis of the SIT Copilot frontend codebase, focusing on responsive design implementation, UI framework, styling approach, and component architecture.

---

## 1. Frontend Framework & Version

| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 19.2.0 | UI Framework |
| **React DOM** | 19.2.0 | DOM Rendering |
| **Vite** | 7.3.1 | Build Tool |
| **TypeScript** | 5.9.3 | Type Safety |
| **Tailwind CSS** | 4.2.0 | Styling Framework |
| **React Router** | 7.13.0 | Client-side Routing |
| **TanStack Query** | 5.90.21 | Server State Management |
| **Zustand** | 5.0.11 | Client State Management |
| **i18next** | 25.8.13 | Internationalization |

---

## 2. Styling Approach

### Primary Styling: Tailwind CSS v4

The project uses **Tailwind CSS v4** with a modern utility-first approach:

- **Tailwind v4 `@theme` directive** for design tokens (not v3 config)
- **CSS Custom Properties** for theming (light/dark/high-contrast)
- **Component classes** for reusable patterns (`.btn`, `.card`, `.input`, `.badge`)
- **Utility classes** for layout and responsive design

### Design Token System

Located in `/frontend/src/styles/globals.css`:

```css
@theme {
  /* Colors */
  --color-bg-page: #f8fafc;
  --color-bg-surface: #ffffff;
  --color-fg-primary: #0f172a;
  --color-accent: #2563eb;
  
  /* Spacing - 4px base scale */
  --spacing-1: 4px;
  --spacing-2: 8px;
  --spacing-4: 16px;
  --spacing-6: 24px;
  
  /* Border Radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  
  /* Motion */
  --duration-fast: 120ms;
  --duration-base: 180ms;
  --duration-slow: 240ms;
}
```

### Theme Support

Three themes implemented via CSS custom properties:
1. **Light Theme** (default)
2. **Dark Theme** (`data-theme="dark"` or `prefers-color-scheme: dark`)
3. **High Contrast Theme** (`data-theme="high-contrast"`)

---

## 3. Responsive Design Implementation

### Breakpoints Used

Tailwind's default breakpoints are utilized:

| Breakpoint | Min Width | Usage |
|------------|-----------|-------|
| `sm:` | 640px | Small adjustments |
| `md:` | 768px | Medium screens/tablets |
| `lg:` | 1024px | Desktop/laptop |
| `xl:` | 1280px | Large desktop |
| `2xl:` | 1536px | Extra large (not yet used) |

### Responsive Patterns in Use

#### Grid Layouts
```tsx
// LandingPage.tsx
<div className="grid lg:grid-cols-5 gap-12 items-center">
  <div className="lg:col-span-3">...</div>
  <div className="lg:col-span-2">...</div>
</div>

// LecturesPage.tsx
<div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
```

#### Typography Scaling
```tsx
<h1 className="text-4xl md:text-5xl font-bold">
```

#### Conditional Rendering
```tsx
// IconButton.tsx - size variants
const sizeClasses = {
  sm: 'min-h-8 min-w-8 p-1.5',
  md: 'min-h-10 min-w-10 p-2',
  lg: 'min-h-12 min-w-12 p-2.5',
}

// Modal.tsx - responsive width
const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  full: 'max-w-full mx-4',
}

// SideSheet.tsx - responsive width
const sizeClasses = {
  sm: 'w-full max-w-sm',
  md: 'w-full max-w-md',
  lg: 'w-full max-w-lg',
  xl: 'w-full max-w-xl',
}
```

#### Padding Adjustments
```tsx
// AppShell.tsx
<main className="flex-1 p-4 md:p-6 lg:p-8">
```

#### Visibility Toggles
```tsx
// KeyboardShortcutsHelp.tsx
className="hidden sm:inline-flex"
```

---

## 4. Component Structure

### Directory Layout

```
frontend/src/
├── components/
│   ├── common/          # Shared UI components
│   │   ├── AppShell.tsx
│   │   ├── Toast.tsx
│   │   ├── Skeleton.tsx
│   │   ├── EmptyState.tsx
│   │   ├── IconButton.tsx
│   │   ├── ToggleSwitch.tsx
│   │   └── KeyboardShortcutsHelp.tsx
│   └── ui/              # Design system components
│       ├── TopBar.tsx
│       ├── Modal.tsx
│       ├── SideSheet.tsx
│       ├── Tabs.tsx
│       ├── SegmentedControl.tsx
│       └── FormField.tsx
├── features/            # Feature-specific components
│   ├── live/
│   │   └── components/
│   │       ├── TranscriptPanel.tsx
│   │       ├── AssistPanel.tsx
│   │       └── SourcePanel.tsx
│   ├── review/
│   │   └── components/
│   │       └── QAStreamBlocks.tsx
│   └── audio/
│       ├── useSpeechRecognition.ts
│       └── useMicrophoneInput.ts
├── pages/               # Route components
│   ├── landing/
│   ├── lectures/
│   ├── settings/
│   ├── procedure/
│   └── readiness/
├── hooks/               # Custom React hooks
├── contexts/            # React contexts
├── stores/              # Zustand stores
├── lib/                 # Utilities
│   ├── api/
│   ├── stream/
│   ├── i18n/
│   └── a11y/
└── styles/              # Global styles
```

### Key Components

| Component | Responsiveness | Notes |
|-----------|----------------|-------|
| **AppShell** | `p-4 md:p-6 lg:p-8` | Responsive padding |
| **TopBar** | `flex-wrap` | Wraps on small screens |
| **Modal** | Size variants | `sm` to `full` with `max-w-*` |
| **SideSheet** | Responsive width | Drawer-like on mobile |
| **TranscriptPanel** | Fixed height | `h-[calc(100vh-130px)]` |
| **LandingPage** | 5-column grid | 3:2 split on large screens |

---

## 5. Current Responsive Design Status

### Strengths

1. **Tailwind v4 with modern `@theme` syntax** - Future-ready approach
2. **Consistent spacing scale** - 4px base unit throughout
3. **Theme system** - Light/dark/high-contrast support
4. **Accessibility-first** - Focus rings, ARIA labels, skip links
5. **Mobile-first media queries** - `@media (prefers-color-scheme: dark)`
6. **Component size variants** - Consistent sizing across components

### Gaps & Improvement Opportunities

1. **No mobile-specific navigation** - No hamburger menu or mobile nav pattern
2. **Fixed height panels** - TranscriptPanel uses calc(100vh-130px), may break on small screens
3. **Limited sm: breakpoint usage** - Most responsive design starts at md:
4. **No container queries** - Still using viewport-based breakpoints
5. **Sidebar widths fixed** - `w-64`, `w-80` don't adapt to screen size
6. **No responsive typography scale** - Only one example of text scaling
7. **No touch-specific optimizations** - Larger tap targets for mobile

---

## 6. Build Configuration

### Vite Configuration

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
```

### Tailwind Configuration

```javascript
// tailwind.config.js
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: { /* Design tokens via CSS variables */ },
      borderRadius: { /* CSS variables */ },
      spacing: { /* 4px scale */ },
      boxShadow: { /* CSS variables */ },
    },
  },
}
```

---

## 7. Accessibility Considerations

The codebase has strong accessibility features:

- **Focus trap** in Modal component
- **Skip to main content** link in AppShell
- **ARIA labels** throughout components
- **Live regions** for screen reader announcements
- **Reduced motion** support: `@media (prefers-reduced-motion: reduce)`
- **Focus visible** styles for keyboard navigation

---

## 8. Recommendations for Responsive Design Improvements

### High Priority

1. **Add mobile navigation pattern** - Hamburger menu for screens < 768px
2. **Make sidebars responsive** - Collapse to drawer/off-canvas on mobile
3. **Add touch-friendly sizing** - Min 44x44px tap targets per WCAG
4. **Test viewport meta tag** - Ensure proper mobile scaling

### Medium Priority

5. **Add more sm: breakpoints** - Optimize for 640px-768px range
6. **Responsive typography** - Use fluid typography with `clamp()`
7. **Container queries** - Consider for card components
8. **Mobile-first spacing** - Review fixed widths (w-64, w-80)

### Low Priority

9. **Dark mode toggle** - Currently only system preference
10. **Orientation handling** - Landscape/portrait optimizations

---

## 9. Key Files Reference

| File | Purpose |
|------|---------|
| `/frontend/src/styles/globals.css` | Design tokens, themes, component classes |
| `/frontend/tailwind.config.js` | Tailwind configuration |
| `/frontend/src/components/common/AppShell.tsx` | Main layout wrapper |
| `/frontend/src/components/ui/Modal.tsx` | Dialog with size variants |
| `/frontend/src/pages/landing/LandingPage.tsx` | Responsive grid example |
| `/frontend/src/hooks/useTheme.ts` | Theme switching logic |

---

## Summary

The SIT Copilot frontend is built on **React 19.2** with **Tailwind CSS v4**, using a modern design token system with strong accessibility support. Responsive design is implemented using Tailwind's utility classes with focus on desktop/tablet layouts (md:, lg:), but has room for improvement in mobile-specific patterns and touch optimizations.
