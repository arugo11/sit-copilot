/**
 * AppShell Component
 * Based on docs/frontend.md Section 9.2
 * Enhanced with accessibility features per Section 10
 */

import type { ReactNode } from 'react'

export type ConnectionState = 'connecting' | 'live' | 'reconnecting' | 'degraded' | 'error'

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
  locale = 'ja',
  skipLinkLabel = { ja: 'コンテンツへスキップ', en: 'Skip to main content' },
}: AppShellProps) {
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
        {skipLinkLabel[locale]}
      </a>

      {/* Top Bar */}
      {topbar && (
        <header
          className="sticky top-0 z-40 w-full bg-bg-surface border-b border-border"
          role="banner"
        >
          <div className="container mx-auto px-4">
            {topbar}
          </div>
        </header>
      )}

      {/* Main Content Area */}
      <div className="flex">
        {/* Left Sidebar */}
        {sidebar && (
          <aside
            className="w-64 bg-bg-surface border-r border-border min-h-[calc(100vh-60px)]"
            role="complementary"
            aria-label="Sidebar"
          >
            <div className="p-4">
              {sidebar}
            </div>
          </aside>
        )}

        {/* Main Content */}
        <main
          id="main-content"
          className="flex-1 p-4 md:p-6 lg:p-8"
          role="main"
          tabIndex={-1}
        >
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>

        {/* Right Rail */}
        {rightRail && (
          <aside
            className="w-80 bg-bg-surface border-l border-border min-h-[calc(100vh-60px)]"
            role="complementary"
            aria-label="Additional information"
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
        aria-label="Connection status"
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
