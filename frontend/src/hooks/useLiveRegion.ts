/**
 * useLiveRegion Hook
 * Hook for announcing messages to screen readers via live region
 * Based on docs/frontend.md Section 10.5
 */

import { useCallback, useRef, useEffect } from 'react'
import { announceToScreenReader, createAnnouncementThrottle } from '@/lib/a11y'

export type AnnouncementPriority = 'polite' | 'assertive'

interface LiveRegionOptions {
  /** Minimum interval between announcements (ms) */
  throttleMs?: number
  /** Priority level for announcements */
  priority?: AnnouncementPriority
}

/**
 * Hook for announcing messages to screen readers
 *
 * @example
 * ```tsx
 * const announce = useLiveRegion()
 *
 * // Basic announcement
 * announce('Loading complete')
 *
 * // Important announcement (interrupts)
 * announce('Error occurred', 'assertive')
 * ```
 */
export function useLiveRegion(options: LiveRegionOptions = {}) {
  const { throttleMs = 5000, priority = 'polite' } = options

  const throttleRef = useRef(createAnnouncementThrottle(throttleMs))

  // Update throttle when throttleMs changes
  useEffect(() => {
    throttleRef.current = createAnnouncementThrottle(throttleMs)
  }, [throttleMs])

  // Cleanup pending announcements on unmount
  useEffect(() => {
    return () => {
      throttleRef.current.cancel()
    }
  }, [])

  const announce = useCallback(
    (message: string, overridePriority?: AnnouncementPriority) => {
      const announcer = (msg: string) => {
        announceToScreenReader(msg, overridePriority ?? priority)
      }
      throttleRef.current.announce(message, announcer)
    },
    [priority]
  )

  const cancelPending = useCallback(() => {
    throttleRef.current.cancel()
  }, [])

  return { announce, cancelPending }
}

/**
 * Hook specifically for connection state announcements
 * Throttled to prevent spam during frequent reconnections
 */
export function useConnectionAnnouncer() {
  const { announce } = useLiveRegion({ throttleMs: 5000 })

  const announceConnection = useCallback(
    (
      state: 'idle' | 'connecting' | 'live' | 'reconnecting' | 'degraded' | 'error',
      locale: 'ja' | 'en' = 'ja'
    ) => {
      const messages: Record<typeof state, { ja: string; en: string }> = {
        idle: { ja: '待機中', en: 'Idle' },
        connecting: { ja: '接続中', en: 'Connecting' },
        live: { ja: '接続済み', en: 'Connected' },
        reconnecting: { ja: '再接続中', en: 'Reconnecting' },
        degraded: { ja: '接続が不安定です', en: 'Connection is degraded' },
        error: { ja: 'エラーが発生', en: 'Error occurred' },
      }

      const priority = state === 'error' ? 'assertive' : 'polite'
      announce(messages[state][locale], priority)
    },
    [announce]
  )

  return { announceConnection }
}

/**
 * Hook for QA status announcements
 */
export function useQaAnnouncer() {
  const { announce } = useLiveRegion({ throttleMs: 3000 })

  const announceQaStatus = useCallback(
    (status: 'generating' | 'done' | 'error', locale: 'ja' | 'en' = 'ja') => {
      const messages: Record<typeof status, { ja: string; en: string }> = {
        generating: { ja: '質問への回答を生成中', en: 'Generating answer' },
        done: { ja: '回答の生成が完了しました', en: 'Answer generated' },
        error: { ja: '回答の生成に失敗しました', en: 'Failed to generate answer' },
      }

      const priority = status === 'error' ? 'assertive' : 'polite'
      announce(messages[status][locale], priority)
    },
    [announce]
  )

  return { announceQaStatus }
}
