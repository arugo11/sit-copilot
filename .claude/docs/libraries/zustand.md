# Zustand

## Overview
Zustand is a small, fast, and scalable state management solution for React. It's simpler than Redux and has no boilerplate.

## Version Info (2025)
- **Latest**: v5.0.x (major rewrite with better TypeScript support)

## Installation
```bash
npm install zustand

# For devtools, persistence, or immer middleware
npm install zustand/middleware
```

## Basic Setup

### Simple Store
```typescript
import { create } from 'zustand'

interface BearState {
  bears: number
  increase: (by: number) => void
  decrease: (by: number) => void
  reset: () => void
}

const useBearStore = create<BearState>()((set) => ({
  bears: 0,
  increase: (by) => set((state) => ({ bears: state.bears + by })),
  decrease: (by) => set((state) => ({ bears: state.bears - by })),
  reset: () => set({ bears: 0 }),
}))

// Usage in component
function BearCounter() {
  const bears = useBearStore((state) => state.bears)
  return <span>{bears} bears</span>
}

function Controls() {
  const increase = useBearStore((state) => state.increase)
  return <button onClick={() => increase(1)}>Increase</button>
}
```

### TypeScript Store Pattern (v5)
```typescript
import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

interface AuthState {
  user: { id: string; name: string } | null
  token: string | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

type AuthStore = AuthState & {
  _hasHydrated: boolean
  setHasHydrated: (state: boolean) => void
}

export const useAuthStore = create<AuthStore>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        user: null,
        token: null,
        isAuthenticated: false,
        _hasHydrated: false,
        setHasHydrated: (state) => set({ _hasHydrated: state }),
        
        // Actions
        login: async (email, password) => {
          const response = await fetch('/api/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
          })
          const { user, token } = await response.json()
          set({ user, token, isAuthenticated: true })
        },
        
        logout: () => {
          set({ user: null, token: null, isAuthenticated: false })
        },
      }),
      {
        name: 'auth-storage',
        partialize: (state) => ({
          user: state.user,
          token: state.token,
          isAuthenticated: state.isAuthenticated,
        }),
        onRehydrateStorage: () => (state) => {
          state?.setHasHydrated(true)
        },
      }
    ),
    { name: 'AuthStore' }
  )
)
```

## Middleware Patterns

### 1. DevTools Middleware
```typescript
import { devtools } from 'zustand/middleware'

const useStore = create(
  devtools(
    (set, get) => ({
      // ... store implementation
    }),
    { name: 'MyStore', enabled: process.env.NODE_ENV === 'development' }
  )
)
```

### 2. Persist Middleware
```typescript
import { persist } from 'zustand/middleware'

const useStore = create(
  persist(
    (set) => ({
      theme: 'light' as 'light' | 'dark',
      toggleTheme: () => set((state) => ({
        theme: state.theme === 'light' ? 'dark' : 'light'
      })),
    }),
    {
      name: 'theme-storage',
      // Use sessionStorage instead of localStorage
      getStorage: () => sessionStorage,
    }
  )
)
```

### 3. Immer Middleware (for Deep Updates)
```typescript
import { immer } from 'zustand/middleware/immer'

interface TodoState {
  todos: Array<{ id: number; text: string; done: boolean }>
  addTodo: (text: string) => void
  toggleTodo: (id: number) => void
}

const useTodoStore = create<TodoState>()(
  immer((set) => ({
    todos: [],
    addTodo: (text) => set((state) => {
      state.todos.push({ id: Date.now(), text, done: false })
    }),
    toggleTodo: (id) => set((state) => {
      const todo = state.todos.find((t) => t.id === id)
      if (todo) todo.done = !todo.done
    }),
  }))
)
```

### 4. Combining Multiple Middlewares
```typescript
import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import { immer } from 'zustand/middleware/immer'

const useStore = create(
  devtools(
    persist(
      immer((set, get) => ({
        // ... store implementation
      })),
      { name: 'my-storage' }
    ),
    { name: 'MyStore' }
  )
)
```

## Advanced Patterns

### 1. Slice Pattern (for Larger Stores)
```typescript
// slices/authSlice.ts
interface AuthSlice {
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const createAuthSlice: StateCreator<
  AppState,
  [],
  [],
  AuthSlice
> = (set) => ({
  user: null,
  token: null,
  login: async (email, password) => { /* ... */ },
  logout: () => set({ user: null, token: null }),
})

// slices/uiSlice.ts
interface UISlice {
  sidebarOpen: boolean
  toggleSidebar: () => void
}

const createUISlice: StateCreator<
  AppState,
  [],
  [],
  UISlice
> = (set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
})

// store/index.ts
import { create } from 'zustand'

type AppState = AuthSlice & UISlice

export const useStore = create<AppState>()((...a) => ({
  ...createAuthSlice(...a),
  ...createUISlice(...a),
}))
```

### 2. Selectors for Computed Values
```typescript
const useStore = create((set, get) => ({
  items: [{ price: 10 }, { price: 20 }],
  getTotal: () => {
    return get().items.reduce((sum, item) => sum + item.price, 0)
  },
}))

// Or using selector hooks
const useTotal = () => useStore((state) => state.getTotal())
```

### 3. Async Actions
```typescript
const useStore = create((set) => ({
  data: null,
  loading: false,
  error: null,
  fetchData: async (id: string) => {
    set({ loading: true, error: null })
    try {
      const response = await fetch(`/api/data/${id}`)
      const data = await response.json()
      set({ data, loading: false })
    } catch (error) {
      set({ error: error.message, loading: false })
    }
  },
}))
```

### 4. React Integration with Hooks
```typescript
// Subscribe to specific slices to prevent unnecessary re-renders
const bears = useBearStore((state) => state.bears)
const increase = useBearStore((state) => state.increase)

// Or use shallow comparison for objects
import { shallow } from 'zustand/shallow'

const { bears, increase } = useBearStore(
  (state) => ({ bears: state.bears, increase: state.increase }),
  shallow
)
```

## Best Practices

1. **Use TypeScript**: Define clear interfaces for state
2. **Use selectors**: Select only what you need
3. **Use shallow comparison**: When selecting multiple values
4. **Split large stores**: Use the slice pattern
5. **Use middleware**: DevTools, persist, immer for common needs
6. **Keep actions pure**: Avoid side effects in actions
7. **Use async/await**: For async actions

## Common Pitfalls

### 1. Subscribing to Entire Store
```tsx
// ❌ Re-renders on every state change
const store = useStore()

// ✅ Only re-renders when bears change
const bears = useStore((state) => state.bears)
```

### 2. Stale State in Async Actions
```typescript
// ❌ May use stale state
setTimeout(() => {
  set({ count: get().count + 1 })
}, 1000)

// ✅ Use the callback form
setTimeout(() => {
  set((state) => ({ count: state.count + 1 }))
}, 1000)
```

### 3. Persist Hydration Issues
```typescript
// Wait for hydration before rendering
const hasHydrated = useAuthStore((state) => state._hasHydrated)

if (!hasHydrated) {
  return <div>Loading...</div>
}
```

## Official Resources
- [Zustand Documentation](https://zustand-demo.pmnd.rs/)
- [GitHub Repository](https://github.com/pmndrs/zustand)
- [Migration Guide v4 to v5](https://github.com/pmndrs/zustand/releases/tag/v5.0.0)
