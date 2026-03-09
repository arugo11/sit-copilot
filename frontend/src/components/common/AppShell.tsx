/**
 * AppShell Component
 * Based on docs/frontend.md Section 9.2
 * Enhanced with accessibility features per Section 10
 */

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useTheme } from '@/hooks/useTheme'
import { useIsMobile } from '@/hooks'

export type ConnectionState =
  | 'idle'
  | 'connecting'
  | 'live'
  | 'reconnecting'
  | 'degraded'
  | 'error'

interface AppShellProps {
  children: ReactNode
  topbar?: ReactNode
  sidebar?: ReactNode
  rightRail?: ReactNode
  /** Connection state for live region announcements */
  connectionState?: ConnectionState
  /** Current locale for announcements */
  locale?: 'ja' | 'en'
  /** Skip to main content link label */
  skipLinkLabel?: { ja: string; en: string }
}

export function AppShell({
  children,
  topbar,
  sidebar,
  rightRail,
  locale,
  skipLinkLabel,
}: AppShellProps) {
  const { t, i18n } = useTranslation()
  const { theme, toggleTheme } = useTheme()
  const isMobile = useIsMobile()
  const resolvedLocale: 'ja' | 'en' =
    locale ??
    ((i18n.resolvedLanguage ?? i18n.language).startsWith('en') ? 'en' : 'ja')
  const jaT = i18n.getFixedT('ja')
  const enT = i18n.getFixedT('en')
  const effectiveSkipLinkLabel =
    skipLinkLabel ?? {
      ja: jaT('a11y.skipToMain'),
      en: enT('a11y.skipToMain'),
    }

  return (
    <div className="min-h-screen bg-bg-page">
      {/* Skip to main content link for keyboard users */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-accent focus:text-white focus:rounded-md focus:shadow-lg"
        onClick={(e) => {
          e.preventDefault()
          document.getElementById('main-content')?.focus()
        }}
      >
        {effectiveSkipLinkLabel[resolvedLocale]}
      </a>

      {/* Top Bar */}
      {topbar && (
        <header
          className="sticky top-0 z-40 w-full bg-bg-surface border-b border-border"
          role="banner"
        >
          <div className="mx-auto flex w-full max-w-7xl items-center px-4">
            <div className="flex-1">{topbar}</div>
            {/* Theme toggle */}
            <button
              type="button"
              onClick={toggleTheme}
              className="ml-2 btn btn-ghost p-2 text-fg-secondary hover:text-fg-primary"
              aria-label={
                theme === 'dark'
                  ? t('appShell.theme.switchToLight')
                  : t('appShell.theme.switchToDark')
              }
              title={
                theme === 'dark'
                  ? t('appShell.theme.light')
                  : t('appShell.theme.dark')
              }
            >
              {theme === 'dark'
                ? /* Sun icon */
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m8.66-9h-1M4.34 12h-1m15.07-6.07-.707.707M6.343 17.657l-.707.707m12.728 0-.707-.707M6.343 6.343l-.707-.707M12 5a7 7 0 1 0 0 14A7 7 0 0 0 12 5z" />
                </svg>
                : /* Moon icon */
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              }
            </button>
          </div>
        </header>
      )}

      {/* Main Content Area */}
      <div className="mx-auto flex w-full max-w-7xl flex-col lg:flex-row">
        {/* Left Sidebar */}
        {sidebar && (
          <aside
            className="order-2 border-t border-border bg-bg-surface lg:order-1 lg:min-h-[calc(100vh-60px)] lg:w-64 lg:border-t-0 lg:border-r"
            role="complementary"
            aria-label={t('appShell.sidebarLabel')}
          >
            <div className="p-4">
              {sidebar}
            </div>
          </aside>
        )}

        {/* Main Content */}
        <main
          id="main-content"
          className="order-1 min-w-0 flex-1 p-4 md:p-6 lg:order-2 lg:p-8"
          role="main"
          tabIndex={-1}
        >
          <div className="mx-auto max-w-7xl">
            {children}
          </div>
        </main>

        {/* Right Rail */}
        {rightRail && (
          <aside
            className="order-3 border-t border-border bg-bg-surface lg:min-h-[calc(100vh-60px)] lg:w-80 lg:border-t-0 lg:border-l"
            role="complementary"
            aria-label={
              isMobile
                ? t('appShell.rightRailLabel')
                : t('appShell.rightRailLabel')
            }
          >
            <div className="p-4">
              {rightRail}
            </div>
          </aside>
        )}
      </div>

      {/* Live Regions for Screen Readers */}
      {/* Polite region for general announcements */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        id="live-region"
      />

      {/* Assertive region for important/error announcements */}
      <div
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
        id="live-region-assertive"
      />

      {/* Status region for connection state */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        id="connection-status-region"
        aria-label={t('appShell.connectionStatusRegion')}
      />
    </div>
  )
}

/**
 * Hook result with announcement method
 */
export interface AppShellHandle {
  /** Announce connection state change */
  announceConnectionState: (state: ConnectionState) => void
  /** Announce general message */
  announce: (message: string, priority?: 'polite' | 'assertive') => void
}
