# Tailwind CSS Library Documentation

## Version
Tailwind CSS v4.2.0

## Configuration

### Package Installation
```json
{
  "dependencies": {
    "@tailwindcss/postcss": "^4.2.0",
    "tailwindcss": "^4.2.0"
  }
}
```

### File Structure
```
frontend/
├── tailwind.config.js    # Legacy config (minimal)
├── src/
│   ├── index.css         # Main entry with @import
│   └── styles/
│       └── globals.css   # @theme directive & custom styles
```

### Current @theme Configuration

```css
@theme {
  /* Colors */
  --color-bg-page: #f8fafc;
  --color-bg-surface: #ffffff;
  --color-bg-muted: #f1f5f9;
  --color-fg-primary: #0f172a;
  --color-fg-secondary: #475569;
  --color-fg-inverse: #ffffff;
  --color-accent: #2563eb;
  --color-accent-weak: #dbeafe;
  --color-success: #16a34a;
  --color-warning: #d97706;
  --color-danger: #dc2626;
  --color-border: #e2e8f0;
  --color-focus: #2563eb;

  /* Border Radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-pill: 999px;

  /* Spacing - 4px base scale */
  --spacing-1: 4px;
  --spacing-2: 8px;
  --spacing-3: 12px;
  --spacing-4: 16px;
  --spacing-5: 20px;
  --spacing-6: 24px;
  --spacing-8: 32px;
  --spacing-10: 40px;
  --spacing-12: 48px;

  /* Shadow */
  --shadow-sm: 0 1px 2px rgb(15 23 42 / 0.06);
  --shadow-md: 0 6px 20px rgb(15 23 42 / 0.10);
  --shadow-lg: 0 12px 32px rgb(15 23 42 / 0.14);

  /* Motion */
  --duration-fast: 120ms;
  --duration-base: 180ms;
  --duration-slow: 240ms;
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
}
```

### Theme Variants

#### Dark Theme (Auto)
```css
@media (prefers-color-scheme: dark) {
  @theme {
    --color-bg-page: #0f172a;
    --color-bg-surface: #1e293b;
    --color-bg-muted: #334155;
    --color-fg-primary: #f8fafc;
    --color-fg-secondary: #cbd5e1;
    --color-fg-inverse: #0f172a;
    --color-border: #475569;
  }
}
```

#### Dark Theme (Manual)
```css
[data-theme="dark"] {
  /* Dark theme tokens */
}
```

#### High Contrast Theme
```css
[data-theme="high-contrast"] {
  --color-bg-page: #ffffff;
  --color-bg-surface: #ffffff;
  --color-bg-muted: #e6e6e6;
  --color-fg-primary: #000000;
  --color-fg-secondary: #000000;
  --color-fg-inverse: #ffffff;
  --color-accent: #0000ff;
  --color-accent-weak: #c8c8ff;
  --color-border: #000000;
}
```

## Default Breakpoints

| Prefix | Min Width | Usage |
|--------|-----------|-------|
| (none) | 0px | Mobile first |
| sm: | 640px | Large tablets |
| md: | 768px | Small laptops |
| lg: | 1024px | Desktops |
| xl: | 1280px | Large desktops |
| 2xl: | 1536px | Extra large |

## Accessibility Features

### Focus Styles
```css
*:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

*:focus:not(:focus-visible) {
  outline: none;
}
```

### Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0ms !important;
    transition-duration: 0ms !important;
  }
}
```

### Screen Reader Utilities
```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
```

## Touch Target Compliance

### Button Styles
```css
.btn {
  min-height: 40px;  /* WCAG 2.2 AA requires 24px, AAA requires 44px */
  min-width: 40px;
}
```

**Status**: 40pxはWCAG 2.2 AA（24px）を満たすが、AAA（44px）には4px不足

## Constraints & Considerations

1. **No container queries support**: Tailwind v4 has limited container query support
2. **Mobile-first required**: All responsive utilities start with mobile base styles
3. **Dark theme**: Uses both auto (prefers-color-scheme) and manual (data-theme)
4. **Touch targets**: Current 40px meets AA but not AAA standard

## Migration Notes from v3

1. **@import instead of @tailwind**: Use `@import "tailwindcss"`
2. **@theme directive**: Replaces most of tailwind.config.js
3. **CSS variables**: All theme values are now CSS custom properties
4. **No JIT mode**: JIT is now the default/only mode

## Sources
- [Tailwind CSS v4 Documentation](https://tailwindcss.com)
- [Tailwind CSS v4 Release Notes](https://github.com/tailwindlabs/tailwindcss/releases)
