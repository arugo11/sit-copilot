# Frontend Implementation Research

**Project**: sit-copilot Lecture Support Application
**Tech Stack**: React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui + TanStack Query/Table/Virtual + Zustand + react-router + react-hook-form + zod + i18next + Framer Motion + WebSocket
**Date**: 2026-02-21
**Researcher**: Researcher Agent

---

## Summary

This document compiles the latest best practices and implementation patterns for the sit-copilot frontend tech stack. The research focuses on Vite 5.x setup, shadcn/ui integration, TanStack Query v5 patterns, Zustand state management, and deployment to Azure Static Web Apps.

---

## Key Technologies

### 1. Vite 5.x + React 18 + TypeScript

**Official Setup**:
\`\`\`bash
npm create vite@latest my-app -- --template react-ts
\`\`\`

**Recommended Configuration**:

\`tsconfig.json\` and \`tsconfig.app.json\`:
\`\`\`json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
\`\`\`

\`vite.config.ts\`:
\`\`\`typescript
import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
\`\`\`

**Best Practices**:
- Use \`@vitejs/plugin-react\` with SWC for faster builds
- Enable path aliases (\`@/*\`) for cleaner imports
- Set \`moduleResolution: "bundler"\` in tsconfig
- Use React 18's \`createRoot\` API
- Leverage concurrent features (Suspense, useTransition)

---

### 2. shadcn/ui

**Critical Understanding**: shadcn/ui is **NOT** a traditional npm package. It's a CLI tool that copies component code directly into your project.

**Installation**:
\`\`\`bash
npx shadcn@latest init
npx shadcn@latest add button
npx shadcn@latest add card
npx shadcn@latest add dialog
\`\`\`

**Integration with Vite** (from official docs):

\`src/index.css\`:
\`\`\`css
@import "tailwindcss";
\`\`\`

\`tsconfig.json\` + \`tsconfig.app.json\`:
\`\`\`json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
\`\`\`

\`vite.config.ts\`:
\`\`\`typescript
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
\`\`\`

**Usage**:
\`\`\`tsx
import { Button } from "@/components/ui/button"

function App() {
  return <Button>Click me</Button>
}
\`\`\`

**Key Points**:
- Components are copied to \`src/components/ui/\`
- Full code ownership and customization
- Built on Radix UI primitives
- Requires Tailwind CSS v3 (v4 compatibility limited)

---

### 3. TanStack Query v5 for React 18

**Core Concepts**:
\`\`\`typescript
import {
  useQuery,
  useMutation,
  useQueryClient,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'

// Create client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,  // 5 minutes
      gcTime: 1000 * 60 * 10,     // 10 minutes (was cacheTime)
      retry: 3,
      refetchOnWindowFocus: false,
    },
  },
})

// Query (v5 syntax - object parameter)
const query = useQuery({
  queryKey: ['todos'],
  queryFn: getTodos,
})

// Mutation
const mutation = useMutation({
  mutationFn: postTodo,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['todos'] })
  },
})
\`\`\`

**v5 Breaking Changes**:
- Object syntax for all hooks (no positional parameters)
- \`gcTime\` instead of \`cacheTime\`
- \`useSuspenseQuery\` for Suspense boundaries
- \`queryKeyFactory\` pattern for key management

**Query Key Factory Pattern**:
\`\`\`typescript
const queryKeys = {
  all: ['users'] as const,
  lists: () => [...queryKeys.all, 'list'] as const,
  list: (filters: string) => [...queryKeys.lists(), { filters }] as const,
  details: () => [...queryKeys.all, 'detail'] as const,
  detail: (id: number) => [...queryKeys.details(), id] as const,
}
\`\`\`

---

### 4. Zustand State Management

**Installation**:
\`\`\`bash
npm install zustand
\`\`\`

**Basic Store Pattern**:
\`\`\`typescript
import { create } from 'zustand'

const useStore = create((set) => ({
  bears: 0,
  increasePopulation: () => set((state) => ({ bears: state.bears + 1 })),
  removeAllBears: () => set({ bears: 0 }),
  updateBears: (newBears) => set({ bears: newBears }),
}))

// Use in components
function BearCounter() {
  const bears = useStore((state) => state.bears)
  return <h1>{bears} around here...</h1>
}
\`\`\`

**Key Features (2025 State)**:
- Minimal API: only \`create\` and hook-based consumption
- No Provider needed
- Zero boilerplate
- TypeScript-first with full type inference
- Based on \`useSyncExternalStore\` (React 18+)
- Built-in middleware: persist, devtools, immer

---

### 5. Azure Static Web Apps Deployment

**Configuration**:
- **App Location**: \`/\` (root)
- **API Location**: (empty or specify if needed)
- **Output Location**: \`dist\` (Vite's default)
- **Build Command**: \`npm run build\`

**Workflow**:
1. Push to connected GitHub/GitLab branch
2. Azure automatically builds and deploys
3. SPA routing handled automatically

---

### 6. WCAG 2.2 AA Accessibility

**Key Requirements**:

**Focus Management**:
- Visible focus indicators
- Focus trapping in modals/dropdowns
- Focus restoration after dynamic changes

**Keyboard Accessibility**:
- All interactive elements keyboard accessible
- Support standard keys (Tab, Enter, Space, Arrows)
- Logical tab order
- No keyboard traps

**Semantic HTML & ARIA**:
- Use semantic elements (\`<button>\`, \`<nav>\`, \`<main>\`)
- Proper ARIA attributes (labels, roles, states)
- \`aria-label\`, \`aria-labelledby\`, \`aria-describedby\`
- Proper heading hierarchy

**Color & Contrast**:
- Minimum 4.5:1 for normal text (AA)
- Minimum 3:1 for large text and UI components
- Don't rely on color alone

---

### 7. WebSocket Integration with TanStack Query

**Pattern**:
- Use TanStack Query for REST API calls
- Use native WebSocket API for real-time updates
- Combine: Query fetches initial data, WebSocket provides updates
- Invalidate queries on WebSocket events

---

## Architecture Recommendations

### Directory Structure
\`\`\`
src/
├── components/
│   └── ui/              # shadcn/ui components
├── hooks/               # Custom hooks
├── pages/               # Route components
├── lib/                 # Utilities (cn function, etc.)
├── stores/              # Zustand stores
├── services/            # API clients
├── types/               # TypeScript types
├── i18n/                # i18next configuration
└── App.tsx
\`\`\`

### Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| shadcn/ui via CLI | Code ownership, full customization, no npm package dependency |
| TanStack Query v5 object syntax | Type safety, better IDE support, consistent API |
| Zustand for state | Minimal boilerplate, TypeScript-first, no Provider needed |
| Azure Static Web Apps | Built-in CI/CD, free tier, automatic HTTPS |
| Path aliases (@/) | Cleaner imports, better refactoring |

---

## Sources

- [shadcn/ui Vite Installation Guide](https://ui.shadcn.com/docs/installation/vite)
- [TanStack Query Quick Start](https://tanstack.com/query/latest/docs/framework/react/quick-start)
- [Zustand Documentation](https://docs.pmnd.rs/zustand/getting-started/introduction)
- [Vite + Tailwind + shadcn-ui 2026 Guide](https://cloud.tencent.com/developer/article/2623006)
- [Shadcn UI Deep Dive](https://juejin.cn/post/7600637595944812586)
- [Zustand TypeScript Guide (2025)](https://m.blog.csdn.net/gitblog_00462/article/details/154814464)

---

## Next Steps

1. **Architect** should review this research and design the component architecture
2. **Implementation Team** should set up the Vite project with recommended configurations
3. **Testing** should include accessibility audit (WCAG 2.2 AA compliance)
4. **Deployment** should configure Azure Static Web Apps with proper build settings
