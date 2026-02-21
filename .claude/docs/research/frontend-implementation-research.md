# Frontend Implementation Research Summary

**Date**: 2025-02-21
**Scope**: Frontend technology stack for sit-copilot web application

## Executive Summary

This research documents 8 key frontend technologies for implementing a modern React web application. All libraries are production-ready, well-maintained, and have strong TypeScript support.

## Technologies Covered

| Technology | Version (2025) | Purpose |
|------------|----------------|---------|
| Vite | 5.4.x | Build tool & dev server |
| shadcn/ui + Radix UI | 2.x + 1.x | Component primitives & UI library |
| TanStack Query | 5.60.x | Data fetching & caching |
| TanStack Table + Virtual | 8.x + 3.x | Data tables with virtualization |
| Zustand | 5.0.x | State management |
| Framer Motion | 12.x | Animations & gestures |
| react-hook-form + zod | 7.x + 3.x | Form handling & validation |
| i18next | 24.x + 15.x | Internationalization |

## Key Findings

### 1. Vite 5.x: Modern Build Tool
- **Instant server start**: No bundling in dev, uses native ES modules
- **Breaking changes from v4**: `cacheTime` renamed to `gcTime` in React Query, CJS to ESM migration
- **Best practice**: Use `@vitejs/plugin-react` with TypeScript, configure path aliases in both `vite.config.ts` and `tsconfig.json`
- **Pitfall**: Don't use `process.env` - use `import.meta.env.VITE_*` instead

### 2. shadcn/ui + Radix UI: Component Primitives
- **Not a DLL**: Components are copied to your project, not installed as packages
- **Installation**: `npx shadcn@latest init` then `npx shadcn@latest add <component>`
- **Radix primitives**: Unstyled, accessible primitives for dialogs, dropdowns, toasts, etc.
- **Pitfall**: Updates require overwriting files (`--overwrite` flag), not automatic like npm packages

### 3. TanStack Query v5: Data Fetching
- **Major change from v4**: `cacheTime` → `gcTime`, better TypeScript types
- **Best practices**: Use query keys as dependencies, set appropriate `staleTime`, handle errors at boundaries
- **React 18 integration**: Full support for Suspense and concurrent rendering
- **Pitfall**: Not handling `null`/`undefined` IDs - use `enabled: !!id` for conditional queries

### 4. TanStack Table + Virtual: Large Data Rendering
- **Headless UI**: Build your own UI, use hooks for logic
- **Virtualization**: Essential for rendering 1000+ rows efficiently
- **Best practice**: Memoize columns, use unique row IDs, estimate row sizes accurately
- **Pitfall**: Not memoizing columns causes re-renders

### 5. Zustand 5.0: State Management
- **Simpler than Redux**: No boilerplate, no providers needed
- **Middleware**: DevTools, persist, immer for deep updates
- **Best practice**: Use selectors to prevent unnecessary re-renders, slice pattern for large stores
- **Pitfall**: Subscribing to entire store causes re-renders on every change

### 6. Framer Motion 12.x: Animations
- **Layout animations**: Use `layout` prop for automatic layout transitions
- **Gestures**: Built-in drag, hover, pan support
- **Performance**: Animate `transform` and `opacity` for GPU acceleration
- **Pitfall**: Exit animations require `AnimatePresence` wrapper

### 7. react-hook-form + zod: Form Validation
- **Integration**: Use `@hookform/resolvers/zod` for schema validation
- **Performance**: Minimal re-renders, controlled components
- **Best practice**: Infer types from Zod schema for type safety
- **Pitfall**: Not resetting form after submit, missing `useFieldArray` for dynamic fields

### 8. i18next: Internationalization
- **React 18 support**: Full Suspense integration
- **Code-splitting**: Load namespaces per route for smaller bundles
- **Best practice**: Feature-based namespaces (common, auth, dashboard, etc.)
- **Pitfall**: Hardcoded strings, complex nested keys

## Recommended Stack

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "@tanstack/react-query": "^5.60.0",
    "@tanstack/react-table": "^8.20.0",
    "@tanstack/react-virtual": "^3.10.0",
    "zustand": "^5.0.0",
    "framer-motion": "^12.0.0",
    "react-hook-form": "^7.54.0",
    "zod": "^3.24.0",
    "@hookform/resolvers": "^3.9.0",
    "i18next": "^24.0.0",
    "react-i18next": "^15.0.0",
    "i18next-browser-languagedetector": "^8.0.0",
    "i18next-http-backend": "^3.0.0",
    "@radix-ui/react-dialog": "^1.1.0",
    "@radix-ui/react-dropdown-menu": "^2.1.0",
    "class-variance-authority": "^0.7.0",
    "tailwind-merge": "^2.5.0",
    "clsx": "^2.1.0"
  },
  "devDependencies": {
    "vite": "^5.4.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.6.0",
    "tailwindcss": "^3.4.0"
  }
}
```

## Architecture Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer                             │
│  shadcn/ui components + Framer Motion animations            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     Data Fetching Layer                     │
│  TanStack Query (server state) + Zustand (client state)     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     Form Validation Layer                   │
│  react-hook-form + zod schema validation                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│  TanStack Table (with Virtual) for large data sets          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Internationalization                      │
│  i18next with code-splitting per namespace/route            │
└─────────────────────────────────────────────────────────────┘
```

## Next Steps

1. **Initialize project with Vite**: `npm create vite@latest frontend -- --template react-ts`
2. **Install dependencies**: Add all libraries from recommended stack
3. **Setup shadcn/ui**: Run `npx shadcn@latest init`
4. **Configure i18next**: Create i18n config and locale files
5. **Setup TanStack Query**: Wrap app in QueryClientProvider
6. **Create base components**: Start with shadcn/ui components

## File Locations

Individual library documentation:
- `.claude/docs/libraries/vite.md`
- `.claude/docs/libraries/shadcn-ui.md`
- `.claude/docs/libraries/tanstack-query.md`
- `.claude/docs/libraries/tanstack-table.md`
- `.claude/docs/libraries/zustand.md`
- `.claude/docs/libraries/framer-motion.md`
- `.claude/docs/libraries/react-hook-form-zod.md`
- `.claude/docs/libraries/i18next.md`
