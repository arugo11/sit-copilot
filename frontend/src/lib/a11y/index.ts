/**
 * Accessibility Utilities
 * Based on docs/frontend.md Section 10
 */

/**
 * Announce message to screen readers via live region
 */
export function announceToScreenReader(message: string, priority: 'polite' | 'assertive' = 'polite'): void {
  const liveRegionId = priority === 'assertive' ? 'live-region-assertive' : 'live-region'

  let liveRegion = document.getElementById(liveRegionId)

  if (!liveRegion) {
    liveRegion = document.createElement('div')
    liveRegion.id = liveRegionId
    liveRegion.setAttribute('aria-live', priority)
    liveRegion.setAttribute('aria-atomic', 'true')
    liveRegion.className = 'sr-only'
    document.body.appendChild(liveRegion)
  }

  // Clear content first to ensure same message is announced again
  liveRegion.textContent = ''
  // Use setTimeout to ensure screen reader picks up the change
  setTimeout(() => {
    liveRegion!.textContent = message
  }, 0)
}

/**
 * Check if user prefers reduced motion
 */
export function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Get all focusable elements within a container
 */
export function getFocusableElements(container: HTMLElement): HTMLElement[] {
  const focusableSelectors = [
    'a[href]',
    'button:not([disabled])',
    'textarea:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ].join(', ')

  return Array.from(container.querySelectorAll<HTMLElement>(focusableSelectors))
}

/**
 * Get the first and last focusable elements within a container
 */
export function getFocusBoundaries(container: HTMLElement): {
  first: HTMLElement | null
  last: HTMLElement | null
} {
  const focusable = getFocusableElements(container)
  return {
    first: focusable[0] ?? null,
    last: focusable[focusable.length - 1] ?? null,
  }
}

/**
 * Trap focus within a container (for modals, dialogs, etc.)
 */
export function trapFocus(event: KeyboardEvent, container: HTMLElement): void {
  if (event.key !== 'Tab') return

  const { first, last } = getFocusBoundaries(container)

  if (!first || !last) return

  if (event.shiftKey) {
    // Shift+Tab: going backwards
    if (document.activeElement === first) {
      event.preventDefault()
      last.focus()
    }
  } else {
    // Tab: going forwards
    if (document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }
}

/**
 * Create a focus trap controller for modals and side sheets
 */
export function createFocusTrap(container: HTMLElement) {
  let previousActiveElement: HTMLElement | null = null
  let observer: MutationObserver | null = null

  const activate = () => {
    // Store the currently focused element
    previousActiveElement = document.activeElement as HTMLElement

    // Focus the first focusable element or the container itself
    const { first } = getFocusBoundaries(container)
    const target = first ?? container
    target.focus()

    // Set up tab key trapping
    const handleTab = (e: KeyboardEvent) => trapFocus(e, container)
    document.addEventListener('keydown', handleTab)

    // Watch for DOM changes to update focusable elements
    observer = new MutationObserver(() => {
      // Re-evaluating focusable elements on content change
    })
    observer.observe(container, { childList: true, subtree: true })

    return () => {
      document.removeEventListener('keydown', handleTab)
      observer?.disconnect()
    }
  }

  const deactivate = () => {
    observer?.disconnect()
    // Restore focus to the previously focused element
    previousActiveElement?.focus()
  }

  return { activate, deactivate }
}

/**
 * Generate a unique ID for accessibility relationships
 */
let idCounter = 0
export function generateA11yId(prefix: string = 'a11y'): string {
  return `${prefix}-${++idCounter}`
}

/**
 * Throttle announcements to prevent screen reader spam
 * Based on docs/frontend.md Section 10.5: loading announcements should be >=5s apart
 */
class AnnouncementThrottle {
  private lastAnnouncementTime = 0
  private minInterval: number
  private pendingMessage: string | null = null
  private pendingTimer: ReturnType<typeof setTimeout> | null = null

  constructor(minInterval: number = 5000) {
    this.minInterval = minInterval
  }

  announce(message: string, announcer: (msg: string) => void): void {
    const now = Date.now()
    const timeSinceLastAnnouncement = now - this.lastAnnouncementTime

    if (timeSinceLastAnnouncement >= this.minInterval) {
      // Can announce immediately
      announcer(message)
      this.lastAnnouncementTime = now
      this.clearPending()
    } else {
      // Schedule announcement for later
      this.schedulePending(message, announcer, this.minInterval - timeSinceLastAnnouncement)
    }
  }

  private schedulePending(message: string, announcer: (msg: string) => void, delay: number): void {
    this.clearPending()
    this.pendingMessage = message
    this.pendingTimer = setTimeout(() => {
      if (this.pendingMessage) {
        announcer(this.pendingMessage)
        this.lastAnnouncementTime = Date.now()
        this.pendingMessage = null
      }
    }, delay)
  }

  private clearPending(): void {
    if (this.pendingTimer) {
      clearTimeout(this.pendingTimer)
      this.pendingTimer = null
    }
    this.pendingMessage = null
  }

  cancel(): void {
    this.clearPending()
  }
}

export function createAnnouncementThrottle(minInterval: number = 5000): AnnouncementThrottle {
  return new AnnouncementThrottle(minInterval)
}

/**
 * Get the appropriate aria-label for icon-only buttons
 */
export function getIconButtonLabel(
  icon: string,
  action: string,
  context?: string
): string {
  if (context) {
    return `${action} ${context} (${icon})`
  }
  return `${action} (${icon})`
}

/**
 * Check if an element is visually hidden but accessible to screen readers
 */
export function isScreenReaderOnly(element: HTMLElement): boolean {
  const styles = window.getComputedStyle(element)
  const srOnlyClass = element.classList.contains('sr-only')

  const visuallyHidden =
    styles.position === 'absolute' &&
    styles.width === '1px' &&
    styles.height === '1px' &&
    styles.overflow === 'hidden'

  return srOnlyClass || visuallyHidden
}

/**
 * Set up live region for connection state monitoring
 */
export type ConnectionState =
  | 'idle'
  | 'connecting'
  | 'live'
  | 'reconnecting'
  | 'degraded'
  | 'error'

const connectionStateMessages: Record<ConnectionState, { ja: string; en: string }> = {
  idle: { ja: '待機中', en: 'Idle' },
  connecting: { ja: '接続中', en: 'Connecting' },
  live: { ja: '接続済み', en: 'Connected' },
  reconnecting: { ja: '再接続中', en: 'Reconnecting' },
  degraded: { ja: '接続が不安定', en: 'Connection unstable' },
  error: { ja: 'エラーが発生', en: 'Error occurred' },
}

export function announceConnectionState(
  state: ConnectionState,
  locale: 'ja' | 'en' = 'ja'
): void {
  const message = connectionStateMessages[state]?.[locale] ?? state
  announceToScreenReader(message, state === 'error' ? 'assertive' : 'polite')
}

/**
 * Keyboard shortcut key combinations
 */
export const keyboardShortcuts = {
  focusSearch: { keys: ['/'], description: { ja: '検索ボックスにフォーカス', en: 'Focus search' }},
  openSettings: { keys: ['Ctrl', ','], description: { ja: '設定を開く', en: 'Open settings' }},
  toggleTheme: { keys: ['Ctrl', 'Shift', 'T'], description: { ja: 'テーマを切り替え', en: 'Toggle theme' }},
  closeDialog: { keys: ['Escape'], description: { ja: 'ダイアログを閉じる', en: 'Close dialog' }},
  navigateTranscript: {
    keys: ['Ctrl', 'ArrowUp'],
    description: { ja: '字幕を上にスクロール', en: 'Scroll transcript up' }
  },
} as const

export type KeyboardShortcutKey = keyof typeof keyboardShortcuts

/**
 * Format keyboard shortcut for display
 */
export function formatKeyCombo(keys: string[]): string {
  return keys.map((key) => {
    if (key === 'Control') return 'Ctrl'
    if (key === 'Escape') return 'Esc'
    if (key.length === 1) return key.toUpperCase()
    return key
  }).join(' + ')
}
