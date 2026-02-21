# Vite 5.x

## Overview
Vite is a modern frontend build tool that provides instant server start, lightning-fast hot module replacement (HMR), and optimized production builds.

## Version Info (2025)
- **Latest stable**: v5.4.x
- **Next.js style**: Uses esbuild for dev, Rollup for production
- **Node version**: Requires Node.js 18+ / 20+

## Installation

### Create New Project
```bash
# Using npm
npm create vite@latest my-app -- --template react-ts

# Using pnpm
pnpm create vite my-app --template react-ts

# Using bun
bunx create-vite my-app --template react-ts
```

### Add to Existing Project
```bash
npm install -D vite @vitejs/plugin-react
```

## Configuration (vite.config.ts)

### TypeScript React Setup
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
        },
      },
    },
  },
})
```

## tsconfig.json for Vite
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

## Breaking Changes from Vite 4
1. **Rollup 4.x**: Now required by default
2. **CJS to ESM**: Config files must use ESM syntax (`import`/`export`)
3. **`fs` restrictions**: File system access in config is more restricted
4. **`define` patterns**: Must use JSON-compatible values

## Key Features

### 1. Instant Server Start
- No bundling in development mode
- Uses native ES modules
- Sub-second startup even for large projects

### 2. Lightning-Fast HMR
- Only re-transform changed modules
- Preserves application state
- Works with CSS and React Fast Refresh

### 3. Optimized Builds
- Automatic code splitting
- CSS code splitting
- Async chunk loading
- Preload directives

## Common Patterns

### Environment Variables
```typescript
// .env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws

// Access in code
const apiUrl = import.meta.env.VITE_API_URL
```

### Dynamic Imports
```typescript
// Lazy load routes
const Dashboard = lazy(() => import('./pages/Dashboard'))

// Code split heavy components
const HeavyChart = lazy(() => import('./components/HeavyChart'))
```

### CSS Modules
```typescript
// Component.tsx
import styles from './Component.module.css'

function Component() {
  return <div className={styles.container}>...</div>
}
```

## Common Pitfalls

### 1. Using `process.env`
```typescript
// ❌ Wrong
const url = process.env.API_URL

// ✅ Correct
const url = import.meta.env.VITE_API_URL
```

### 2. Absolute Imports Not Working
Make sure both `vite.config.ts` and `tsconfig.json` have matching alias configurations.

### 3. Slow Build Times
```typescript
// Add to vite.config.ts
build: {
  minify: 'esbuild', // faster than terser
  target: 'esnext',
}
```

### 4. Memory Issues in Dev
```typescript
// Limit optimizeDeps
optimizeDeps: {
  exclude: ['your-heavy-dep'],
}
```

## Performance Tips

1. **Use `esbuild` minification**: Faster than terser
2. **Configure manual chunks**: Split vendor code
3. **Enable CSS code splitting**: Automatic with Vite
4. **Use `await` for dynamic imports**: Preload chunks
5. **Monitor bundle size**: Use `vite-plugin-visualizer`

## Commands
```bash
# Development
vite

# Build
vite build

# Preview production build
vite preview

# TypeScript check (via plugin)
vite-plugin-checker
```

## Official Resources
- [Vite Documentation](https://vite.dev/)
- [Vite GitHub](https://github.com/vitejs/vite)
- [Awesome Vite](https://github.com/vitejs/awesome-vite)
