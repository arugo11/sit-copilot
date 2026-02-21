# shadcn/ui + Radix UI

## Overview
- **shadcn/ui**: Copy-paste component collection built with Radix UI primitives
- **Radix UI**: Unstyled, accessible UI primitives for React
- **Key difference**: Not a component library DLL—components are copied to your project

## Version Info (2025)
- **shadcn/ui**: v2.x (major rewrite from v1)
- **Radix UI**: v1.x stable, primitives incrementally updated

## Installation

### Initial Setup
```bash
# Initialize shadcn/ui (interactive)
npx shadcn@latest init

# CLI will ask:
# - TypeScript: Yes
# - Style: Default / New York / Zinc
# - Base color: Slate / Neutral / Stone
# - CSS variables: Yes
# - Import alias: @/*
# - Component path: @/components
```

### Configuration Created
```json
// components.json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/app/globals.css",
    "baseColor": "zinc",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

### Adding Components
```bash
# Single component
npx shadcn@latest add button

# Multiple components
npx shadcn@latest add button dialog dropdown-menu

# All components (not recommended)
npx shadcn@latest add --all
```

## Project Structure
```
src/
├── components/
│   ├── ui/                    # shadcn components (copied here)
│   │   ├── button.tsx
│   │   ├── dialog.tsx
│   │   └── dropdown-menu.tsx
│   └── custom/                # Your custom components
├── lib/
│   └── utils.ts               # cn() helper function
└── app/
    └── globals.css            # CSS variables + Tailwind directives
```

## Key Dependencies
```json
{
  "dependencies": {
    "@radix-ui/react-dialog": "^1.1.2",
    "@radix-ui/react-dropdown-menu": "^2.1.2",
    "@radix-ui/react-select": "^2.1.2",
    "@radix-ui/react-slider": "^1.2.1",
    "@radix-ui/react-slot": "^1.1.0",
    "@radix-ui/react-tabs": "^1.1.1",
    "@radix-ui/react-toast": "^1.2.2",
    "@radix-ui/react-tooltip": "^1.1.4",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.5",
    "cmdk": "^1.0.4",
    "embla-carousel-react": "^8.3.1",
    "lucide-react": "^0.462.0"
  }
}
```

## Common Patterns

### 1. Using Components
```tsx
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog"

export function MyComponent() {
  return (
    <Dialog>
      <DialogContent>
        <DialogHeader>
          <Button variant="default">Click me</Button>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  )
}
```

### 2. Extending Components
```tsx
// Copy the component and modify
import * as React from "react"
import { Button as ShadcnButton } from "@/components/ui/button"

export interface ButtonProps extends React.ComponentProps<typeof ShadcnButton> {
  isLoading?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ isLoading, children, ...props }, ref) => {
    return (
      <ShadcnButton ref={ref} disabled={isLoading} {...props}>
        {isLoading ? <Spinner /> : children}
      </ShadcnButton>
    )
  }
)
```

### 3. Compound Components
```tsx
// Dialog pattern
<Dialog open={open} onOpenChange={setOpen}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Are you sure?</DialogTitle>
    </DialogHeader>
    <DialogFooter>
      <Button onClick={() => setOpen(false)}>Cancel</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

## Radix UI Primitives Reference

| Primitive | Purpose | Key Features |
|-----------|---------|--------------|
| `@radix-ui/react-dialog` | Modal dialogs | Focus trap, escape to close |
| `@radix-ui/react-dropdown-menu` | Dropdown menus | Keyboard navigation |
| `@radix-ui/react-select` | Select inputs | Virtualization for large lists |
| `@radix-ui/react-tabs` | Tab navigation | Keyboard support |
| `@radix-ui/react-toast` | Notifications | Auto-dismiss, stacking |
| `@radix-ui/react-tooltip` | Tooltips | Delay, positioning |
| `@radix-ui/react-popover` | Popover content | Click outside to close |
| `@radix-ui/react-accordion` | Collapsible sections | Single/multiple mode |
| `@radix-ui/react-slider` | Range selection | Multi-thumb support |
| `@radix-ui/react-switch` | Toggle switches | Accessible form controls |
| `@radix-ui/react-avatar` | User avatars | Fallback patterns |
| `@radix-ui/react-progress` | Progress bars | Indeterminate state |
| `@radix-ui/react-scroll-area` | Custom scrollbars | Styled scrollbars |

## Common Pitfalls

### 1. Missing Tailwind CSS Variables
```css
/* Make sure globals.css has these */
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 240 10% 3.9%;
    --primary: 240 5.9% 10%;
    /* ... all variables from shadcn ... */
  }
  
  .dark {
    --background: 240 10% 3.9%;
    --foreground: 0 0% 98%;
    /* ... dark mode variables ... */
  }
}
```

### 2. cn() Helper Missing
```typescript
// src/lib/utils.ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### 3. Updates Don't Apply Automatically
Unlike npm packages, shadcn components are copied to your project. To update:
```bash
npx shadcn@latest add button --overwrite
```

### 4. TypeScript Errors with Variants
Make sure `class-variance-authority` (CVA) is installed:
```bash
npm install class-variance-authority
```

### 5. Portability Issues
Since components are copied to your project, they're not portable. If you need portability, consider using Radix primitives directly.

## Best Practices

1. **Don't modify UI components directly**: Create wrappers instead
2. **Use the cn() helper**: For conditional classes
3. **Follow CVA patterns**: For component variants
4. **Keep components simple**: shadcn components are meant to be primitives
5. **Extend, don't edit**: Create new components that compose shadcn ones

## Official Resources
- [shadcn/ui Documentation](https://ui.shadcn.com/)
- [Radix UI Documentation](https://www.radix-ui.com/)
- [Radix UI Primitives](https://www.radix-ui.com/primitives/docs/overview/introduction)
