/**
 * useKeyboardShortcuts Hook
 * Hook for handling keyboard shortcuts
 * Based on docs/frontend.md Section 10.4
 */

import { useEffect, useCallback, useState, useRef } from 'react'

export interface KeyboardShortcut {
  /** Key combination (e.g., 'Ctrl+K', 'Escape') */
  key: string
  /** Callback when shortcut is triggered */
  callback: (event: KeyboardEvent) => void
  /** Whether the shortcut is currently enabled */
  enabled?: boolean
  /** Prevent default behavior */
  preventDefault?: boolean
}

/**
 * Parse a key combination string into keys
 * e.g., 'Ctrl+Shift+K' -> ['Ctrl', 'Shift', 'K']
 */
function parseKeyCombo(keyCombo: string): {
  ctrl: boolean
  shift: boolean
  alt: boolean
  meta: boolean
  key: string
} {
  const parts = keyCombo.toLowerCase().split('+').map((s) => s.trim())

  return {
    ctrl: parts.includes('ctrl') || parts.includes('control'),
    shift: parts.includes('shift'),
    alt: parts.includes('alt'),
    meta: parts.includes('meta') || parts.includes('cmd') || parts.includes('command'),
    key: parts[parts.length - 1],
  }
}

/**
 * Check if a keyboard event matches a key combination
 */
function matchesKeyCombo(event: KeyboardEvent, keyCombo: string): boolean {
  const parsed = parseKeyCombo(keyCombo)

  // Check modifiers
  if (parsed.ctrl !== (event.ctrlKey || event.metaKey)) return false
  if (parsed.shift !== event.shiftKey) return false
  if (parsed.alt !== event.altKey) return false
  if (parsed.meta !== event.metaKey) return false

  // Check key (handle both 'escape' and 'esc')
  const eventKey = event.key.toLowerCase()
  const targetKey = parsed.key.toLowerCase()

  // Common aliases
  const keyAliases: Record<string, string[]> = {
    esc: ['escape'],
    ctrl: ['control'],
    cmd: ['meta', 'command'],
    return: ['enter'],
  }

  const normalizedEventKey = Object.entries(keyAliases).find(([, aliases]) =>
    aliases.includes(eventKey)
  )?.[0] ?? eventKey

  if (normalizedEventKey === targetKey) return true

  return eventKey === targetKey
}

/**
 * Hook for registering keyboard shortcuts
 *
 * @example
 * ```tsx
 * useKeyboardShortcuts([
 *   { key: 'Ctrl+K', callback: () => openSearch() },
 *   { key: 'Escape', callback: () => closeModal(), enabled: isModalOpen },
 * ])
 * ```
 */
export function useKeyboardShortcuts(shortcuts: KeyboardShortcut[]) {
  const shortcutsRef = useRef(shortcuts)

  // Update ref when shortcuts change
  useEffect(() => {
    shortcutsRef.current = shortcuts
  }, [shortcuts])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      for (const shortcut of shortcutsRef.current) {
        if (shortcut.enabled === false) continue

        if (matchesKeyCombo(event, shortcut.key)) {
          if (shortcut.preventDefault !== false) {
            event.preventDefault()
          }
          shortcut.callback(event)
          return // Only trigger first matching shortcut
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, []) // Empty deps - listener is stable
}

/**
 * Hook for keyboard navigation within a list
 *
 * @example
 * ```tsx
 * const { focusedIndex, keyHandlers } = useKeyboardNavigation({
 *   itemCount: items.length,
 *   onSelect: (index) => selectItem(index),
 * })
 *
 * <ul {...keyHandlers}>
 *   {items.map((item, i) => (
 *     <li key={i} tabIndex={i === focusedIndex ? 0 : -1}>...</li>
 *   ))}
 * </ul>
 * ```
 */
export interface KeyboardNavigationOptions {
  /** Total number of items */
  itemCount: number
  /** Callback when an item is selected (Enter/Space) */
  onSelect?: (index: number) => void
  /** Callback when focused index changes */
  onFocusChange?: (index: number) => void
  /** Initial focused index */
  initialIndex?: number
  /** Wrap navigation (go from last to first) */
  wrap?: boolean
  /** Orientation of the list */
  orientation?: 'vertical' | 'horizontal' | 'both'
}

export function useKeyboardNavigation(options: KeyboardNavigationOptions) {
  const {
    itemCount,
    onSelect,
    onFocusChange,
    initialIndex = 0,
    wrap = true,
    orientation = 'vertical',
  } = options

  const [focusedIndex, setFocusedIndex] = useState(initialIndex)

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      let newIndex = focusedIndex

      switch (event.key) {
        case 'ArrowDown':
          if (orientation === 'vertical' || orientation === 'both') {
            event.preventDefault()
            newIndex = focusedIndex + 1
            if (wrap && newIndex >= itemCount) {
              newIndex = 0
            } else if (newIndex >= itemCount) {
              newIndex = itemCount - 1
            }
          }
          break

        case 'ArrowUp':
          if (orientation === 'vertical' || orientation === 'both') {
            event.preventDefault()
            newIndex = focusedIndex - 1
            if (wrap && newIndex < 0) {
              newIndex = itemCount - 1
            } else if (newIndex < 0) {
              newIndex = 0
            }
          }
          break

        case 'ArrowRight':
          if (orientation === 'horizontal' || orientation === 'both') {
            event.preventDefault()
            newIndex = focusedIndex + 1
            if (wrap && newIndex >= itemCount) {
              newIndex = 0
            } else if (newIndex >= itemCount) {
              newIndex = itemCount - 1
            }
          }
          break

        case 'ArrowLeft':
          if (orientation === 'horizontal' || orientation === 'both') {
            event.preventDefault()
            newIndex = focusedIndex - 1
            if (wrap && newIndex < 0) {
              newIndex = itemCount - 1
            } else if (newIndex < 0) {
              newIndex = 0
            }
          }
          break

        case 'Home':
          event.preventDefault()
          newIndex = 0
          break

        case 'End':
          event.preventDefault()
          newIndex = itemCount - 1
          break

        case 'Enter':
        case ' ':
          event.preventDefault()
          onSelect?.(focusedIndex)
          return

        default:
          return
      }

      if (newIndex !== focusedIndex) {
        setFocusedIndex(newIndex)
        onFocusChange?.(newIndex)
      }
    },
    [focusedIndex, itemCount, onSelect, onFocusChange, wrap, orientation]
  )

  return {
    focusedIndex,
    setFocusedIndex,
    keyHandlers: {
      onKeyDown: handleKeyDown,
      role: 'listbox',
      'aria-activedescendant': `item-${focusedIndex}`,
    },
  }
}
