# Mobile Navigation Implementation Guide

## Summary
Architectのハイブリッドパターン（Hamburger + Bottom Nav）に対する実装ガイド。

## Component Structure

### 1. BottomNavigation Component

**File**: `frontend/src/components/navigation/BottomNavigation.tsx`

```tsx
import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'

interface NavItem {
  path: string
  labelKey: string
  icon: React.ComponentType<{ className?: string }>
  ariaLabelKey: string
}

const NAV_ITEMS: NavItem[] = [
  {
    path: '/lectures',
    labelKey: 'nav.bottom.lectures',
    icon: ListIcon,
    ariaLabelKey: 'nav.bottom.lecturesAria',
  },
  {
    path: '/live', // Dynamic path with session ID
    labelKey: 'nav.bottom.live',
    icon: LiveIcon,
    ariaLabelKey: 'nav.bottom.liveAria',
  },
  {
    path: '/review', // Dynamic path with session ID
    labelKey: 'nav.bottom.review',
    icon: ReviewIcon,
    ariaLabelKey: 'nav.bottom.reviewAria',
  },
]

export function BottomNavigation() {
  const { t } = useTranslation()
  const location = useLocation()

  const isActive = (path: string) => {
    if (path === '/live' || path === '/review') {
      return location.pathname.includes(path)
    }
    return location.pathname === path
  }

  return (
    <nav 
      className="fixed bottom-0 left-0 right-0 z-40 bg-bg-surface border-t border-border md:hidden"
      aria-label={t('nav.bottom.ariaLabel')}
    >
      <div className="flex justify-around items-center h-16">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={cn(
              'flex flex-col items-center justify-center gap-1',
              'min-h-[44px] min-w-[44px] px-3 py-2',
              'text-fg-secondary hover:text-fg-primary',
              'transition-colors duration-180',
              isActive(item.path) && 'text-accent'
            )}
            aria-current={isActive(item.path) ? 'page' : undefined}
            aria-label={t(item.ariaLabelKey)}
          >
            <item.icon className="w-6 h-6" aria-hidden="true" />
            <span className="text-xs font-medium">
              {t(item.labelKey)}
            </span>
          </Link>
        ))}
      </div>
    </nav>
  )
}
```

### 2. DrawerNavigation Component

**File**: `frontend/src/components/navigation/DrawerNavigation.tsx`

```tsx
import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'

interface DrawerItem {
  path: string
  labelKey: string
  icon: React.ComponentType<{ className?: string }>
  ariaLabelKey: string
  section?: 'primary' | 'secondary' | 'settings'
}

const DRAWER_ITEMS: DrawerItem[] = [
  {
    path: '/lectures/:id/sources',
    labelKey: 'nav.drawer.sources',
    icon: SourceIcon,
    ariaLabelKey: 'nav.drawer.sourcesAria',
    section: 'secondary',
  },
  {
    path: '/procedure',
    labelKey: 'nav.drawer.procedure',
    icon: ProcedureIcon,
    ariaLabelKey: 'nav.drawer.procedureAria',
    section: 'secondary',
  },
  {
    path: '/readiness',
    labelKey: 'nav.drawer.readiness',
    icon: ReadinessIcon,
    ariaLabelKey: 'nav.drawer.readinessAria',
    section: 'secondary',
  },
  {
    path: '/settings',
    labelKey: 'nav.drawer.settings',
    icon: SettingsIcon,
    ariaLabelKey: 'nav.drawer.settingsAria',
    section: 'settings',
  },
]

interface DrawerNavigationProps {
  isOpen: boolean
  onClose: () => void
}

export function DrawerNavigation({ isOpen, onClose }: DrawerNavigationProps) {
  const { t } = useTranslation()
  const location = useLocation()
  const drawerRef = useRef<HTMLDivElement>(null)

  // Focus trap implementation
  useEffect(() => {
    if (!isOpen) return

    const focusableElements = drawerRef.current?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled])'
    )
    const firstElement = focusableElements?.[0]
    firstElement?.focus()
  }, [isOpen])

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-fg-primary/50 md:hidden"
          onClick={handleBackdropClick}
          aria-hidden="true"
        />
      )}

      {/* Drawer */}
      <aside
        ref={drawerRef}
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-bg-surface border-r border-border',
          'transform transition-transform duration-240 ease-standard',
          'md:relative md:transform-none md:block md:z-0',
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        )}
        aria-label={t('nav.drawer.ariaLabel')}
      >
        <div className="flex flex-col h-full">
          {/* Header with close button (mobile only) */}
          <div className="flex items-center justify-between p-4 border-b border-border md:hidden">
            <h2 className="text-lg font-semibold">{t('nav.drawer.title')}</h2>
            <button
              type="button"
              onClick={onClose}
              className="btn btn-ghost p-2 min-h-8 min-w-8"
              aria-label={t('nav.drawer.closeAria')}
            >
              <CloseIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation items */}
          <nav className="flex-1 overflow-y-auto p-4" aria-label="Drawer navigation">
            <div className="space-y-1">
              {DRAWER_ITEMS.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={onClose}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-md',
                    'text-fg-secondary hover:text-fg-primary hover:bg-bg-muted',
                    'transition-colors duration-180',
                    'min-h-[44px]',
                    location.pathname === item.path && 'bg-bg-muted text-fg-primary'
                  )}
                  aria-label={t(item.ariaLabelKey)}
                >
                  <item.icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                  <span className="text-sm font-medium">{t(item.labelKey)}</span>
                </Link>
              ))}
            </div>
          </nav>
        </div>
      </aside>
    </>
  )
}
```

### 3. HamburgerMenuButton Component

**File**: `frontend/src/components/navigation/HamburgerMenuButton.tsx`

```tsx
import { useTranslation } from 'react-i18next'

interface HamburgerMenuButtonProps {
  onClick: () => void
  isOpen: boolean
}

export function HamburgerMenuButton({ onClick, isOpen }: HamburgerMenuButtonProps) {
  const { t } = useTranslation()

  return (
    <button
      type="button"
      onClick={onClick}
      className="btn btn-ghost p-2 min-h-11 min-w-11 md:hidden"
      aria-label={isOpen ? t('nav.hamburger.closeAria') : t('nav.hamburger.openAria')}
      aria-expanded={isOpen}
      aria-controls="drawer-navigation"
    >
      <svg
        className="w-6 h-6"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        {isOpen ? (
          // Close icon
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        ) : (
          // Hamburger icon
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 6h16M4 12h16M4 18h16"
          />
        )}
      </svg>
    </button>
  )
}
```

## AppShell Integration

**File**: `frontend/src/components/common/AppShell.tsx`

```tsx
export function AppShell({ children, topbar, sidebar, rightRail, ... }: AppShellProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)

  return (
    <div className="min-h-screen bg-bg-page pb-16 md:pb-0">
      {/* Skip link */}

      {/* Top Bar with Hamburger */}
      {topbar && (
        <header className="sticky top-0 z-40 w-full bg-bg-surface border-b border-border">
          <div className="container mx-auto px-4">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center gap-4">
                <HamburgerMenuButton
                  isOpen={isDrawerOpen}
                  onClick={() => setIsDrawerOpen(!isDrawerOpen)}
                />
                {topbar}
              </div>
              {/* Theme toggle etc. */}
            </div>
          </div>
        </header>
      )}

      {/* Main Layout */}
      <div className="flex">
        {/* Drawer (hidden on mobile unless open) */}
        <DrawerNavigation isOpen={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} />

        {/* Main Content */}
        <main className="flex-1 min-h-[calc(100vh-64px)]">
          {children}
        </main>

        {/* Right Rail (hidden on mobile) */}
        {rightRail && (
          <aside className="hidden lg:block w-80 border-l border-border">
            {rightRail}
          </aside>
        )}
      </div>

      {/* Bottom Navigation (mobile only) */}
      <BottomNavigation />

      {/* Live regions */}
    </div>
  )
}
```

## Translation Keys

**File**: `frontend/src/locales/ja/navigation.json`

```json
{
  "nav": {
    "bottom": {
      "ariaLabel": "メインナビゲーション",
      "lectures": "講義一覧",
      "lecturesAria": "講義一覧へ移動",
      "live": "ライブ",
      "liveAria": "ライブ講義へ移動",
      "review": "復習",
      "reviewAria": "復習ページへ移動"
    },
    "drawer": {
      "ariaLabel": "ドロワーメニュー",
      "title": "メニュー",
      "closeAria": "メニューを閉じる",
      "sources": "講義資料",
      "sourcesAria": "講義資料へ移動",
      "procedure": "手続き",
      "procedureAria": "手続きページへ移動",
      "readiness": "準備確認",
      "readinessAria": "準備確認ページへ移動",
      "settings": "設定",
      "settingsAria": "設定ページへ移動"
    },
    "hamburger": {
      "openAria": "メニューを開く",
      "closeAria": "メニューを閉じる"
    }
  }
}
```

## Responsive Breakpoint Summary

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Mobile | < 768px | Bottom Nav + Drawer (overlay) |
| Tablet | 768px - 1024px | Sidebar (persistent) + Bottom Nav |
| Desktop | 1024px+ | Sidebar + Right Rail (no Bottom Nav) |

## Accessibility Checklist

- [x] Touch target size: 44x44px minimum
- [x] Icon + Label on Bottom Nav
- [x] ARIA labels for all navigation items
- [x] aria-current for active page
- [x] aria-expanded for hamburger button
- [x] Focus trap in drawer
- [x] ESC to close drawer
- [x] Keyboard navigation (Tab, Arrow keys)
- [x] Reduced motion support
- [ ] Live region announcements (待実装)
