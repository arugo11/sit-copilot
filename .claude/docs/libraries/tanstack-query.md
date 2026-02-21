# TanStack Query v5 (React Query)

## Overview
TanStack Query (formerly React Query) is a powerful data synchronization library for React. It handles caching, background updates, and stale data management.

## Version Info (2025)
- **Latest**: v5.60.x
- **Major changes from v4**: New API patterns, better TypeScript support, simplified config

## Installation
```bash
npm install @tanstack/react-query

# For React Native
npm install @tanstack/react-query-platform

# For devtools
npm install -D @tanstack/react-query-devtools
```

## Setup

### Basic Setup (Client-side Rendering)
```tsx
// src/main.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 10,   // 10 minutes (formerly cacheTime)
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>,
)
```

### SSR Setup (Next.js / Remix)
```tsx
// utils/query-client.ts
import { QueryClient } from '@tanstack/react-query'

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
      },
    },
  })
}

let browserQueryClient: QueryClient | undefined = undefined

export function getQueryClient() {
  if (typeof window === 'undefined') {
    // Server: always create a new client
    return makeQueryClient()
  } else {
    // Browser: create once and reuse
    if (!browserQueryClient) browserQueryClient = makeQueryClient()
    return browserQueryClient
  }
}
```

## Breaking Changes from v4

| v4 | v5 | Notes |
|----|----|----|
| `cacheTime` | `gcTime` | Garbage collection time |
| `isFetching` | `isFetching` | No change, but better types |
| `useIsFetching()` | `useIsFetching()` | No change |
| `QueryCache` | `QueryCache` | No change |
| `setQueryData` | `setQueryData` | No change |

## Key Patterns

### 1. Fetching Data (useQuery)
```tsx
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

interface User {
  id: number
  name: string
  email: string
}

function useUser(userId: number) {
  return useQuery({
    queryKey: ['user', userId],
    queryFn: async () => {
      const { data } = await axios.get(`/api/users/${userId}`)
      return data as User
    },
    enabled: !!userId, // Only fetch if userId exists
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

// Usage
function UserProfile({ userId }: { userId: number }) {
  const { data: user, isLoading, error, isError } = useUser(userId)
  
  if (isLoading) return <div>Loading...</div>
  if (isError) return <div>Error: {error.message}</div>
  
  return <div>{user.name}</div>
}
```

### 2. Mutating Data (useMutation)
```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'

function useUpdateUser() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ id, ...data }: { id: number } & Partial<User>) => {
      const { data } = await axios.patch(`/api/users/${id}`, data)
      return data as User
    },
    // Optimistic update
    onMutate: async (variables) => {
      await queryClient.cancelQueries({ queryKey: ['user', variables.id] })
      const previous = queryClient.getQueryData(['user', variables.id])
      queryClient.setQueryData(['user', variables.id], variables)
      return { previous }
    },
    // Rollback on error
    onError: (err, variables, context) => {
      queryClient.setQueryData(['user', variables.id], context?.previous)
    },
    // Always refetch after error or success
    onSettled: (data, error, variables) => {
      queryClient.invalidateQueries({ queryKey: ['user', variables.id] })
    },
  })
}
```

### 3. Infinite Queries (Pagination)
```tsx
function useUsers() {
  return useInfiniteQuery({
    queryKey: ['users'],
    queryFn: async ({ pageParam = 0 }) => {
      const { data } = await axios.get('/api/users', {
        params: { page: pageParam, limit: 20 },
      })
      return data
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (lastPage.length === 0) return undefined
      return allPages.length
    },
  })
}

function UserList() {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useUsers()
  
  return (
    <div>
      {data?.pages.map((page, i) => (
        <div key={i}>
          {page.map(user => <UserCard key={user.id} user={user} />)}
        </div>
      ))}
      {hasNextPage && (
        <button onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
          {isFetchingNextPage ? 'Loading...' : 'Load more'}
        </button>
      )}
    </div>
  )
}
```

### 4. Dependent Queries
```tsx
function useUserPosts(userId: number) {
  const userQuery = useQuery({
    queryKey: ['user', userId],
    queryFn: () => fetchUser(userId),
  })
  
  const postsQuery = useQuery({
    queryKey: ['posts', userId],
    queryFn: () => fetchUserPosts(userId),
    enabled: !!userQuery.data, // Only run when user exists
  })
  
  return { user: userQuery.data, posts: postsQuery.data }
}
```

### 5. Error Handling
```tsx
function useData() {
  return useQuery({
    queryKey: ['data'],
    queryFn: fetchData,
    retry: (failureCount, error) => {
      // Don't retry on 404 or 401
      if (error.status === 404 || error.status === 401) {
        return false
      }
      return failureCount < 3
    },
    onError: (error) => {
      // Global error handler
      console.error('Query error:', error)
    },
  })
}

// Boundary-based error handling
function App() {
  return (
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <DataProvider />
    </ErrorBoundary>
  )
}
```

## Query Key Patterns

```tsx
// Scalar query key
useQuery({ queryKey: ['user'], queryFn: fetchUser })

// Array query key with parameters
useQuery({ queryKey: ['user', userId], queryFn: () => fetchUser(userId) })

// Object query key (for complex parameters)
useQuery({ 
  queryKey: ['users', { page, filters }], 
  queryFn: () => fetchUsers({ page, filters }) 
})

// Hierarchical query keys
useQuery({ queryKey: ['user', userId, 'posts'], queryFn: () => fetchUserPosts(userId) })
```

## Cache Invalidation Patterns

```tsx
// Invalidate all queries
queryClient.invalidateQueries()

// Invalidate specific queries
queryClient.invalidateQueries({ queryKey: ['users'] })

// Invalidate with predicate
queryClient.invalidateQueries({
  predicate: (query) => query.queryKey[0] === 'users'
})

// Reset queries (clear cache)
queryClient.resetQueries({ queryKey: ['users'] })

// Set data directly (optimistic)
queryClient.setQueryData(['user', userId], newUser)
```

## Best Practices

1. **Use query keys as dependencies**: Treat them like useEffect dependencies
2. **Enable queries conditionally**: Use the `enabled` option
3. **Set appropriate staleTime**: Prevent unnecessary refetches
4. **Handle errors at boundaries**: Use ErrorBoundary for global handling
5. **Use mutations for writes**: Separate reads and writes
6. **Optimistic updates**: Update UI immediately, rollback on error
7. **Prefetch data**: Load data before it's needed
8. **Use devtools**: Debug cache state and query flow

## Common Pitfalls

### 1. Not Handling `null` or `undefined` IDs
```tsx
// ❌ Will fetch with undefined
const { data } = useQuery({
  queryKey: ['user', userId],
  queryFn: () => fetchUser(userId),
})

// ✅ Conditional fetch
const { data } = useQuery({
  queryKey: ['user', userId],
  queryFn: () => fetchUser(userId),
  enabled: !!userId,
})
```

### 2. Memory Leaks with Stale Data
```tsx
// Set gcTime to clean up unused queries
useQuery({
  queryKey: ['expensive-data'],
  queryFn: fetchExpensiveData,
  gcTime: 1000 * 60 * 5, // 5 minutes
})
```

### 3. Over-fetching
```tsx
// ❌ Multiple similar queries
useQuery({ queryKey: ['user', 'profile'], queryFn: fetchProfile })
useQuery({ queryKey: ['user', 'settings'], queryFn: fetchSettings })

// ✅ Single query with combined data
useQuery({ 
  queryKey: ['user'], 
  queryFn: async () => {
    const [profile, settings] = await Promise.all([
      fetchProfile(),
      fetchSettings(),
    ])
    return { profile, settings }
  }
})
```

## Official Resources
- [TanStack Query Documentation](https://tanstack.com/query/latest)
- [Migration Guide v4 to v5](https://tanstack.com/query/latest/docs/react/guides/migrating-to-v5)
- [GitHub Repository](https://github.com/TanStack/query)
