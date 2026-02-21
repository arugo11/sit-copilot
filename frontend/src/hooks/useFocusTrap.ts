/**
 * useFocusTrap Hook
 * Hook for trapping focus within a container (for modals, dialogs, etc.)
 * Based on docs/frontend.md Section 10.4
 */

import { useEffect, useRef } from 'react'
import { getFocusableElements, getFocusBoundaries } from '@/lib/a11y'

export interface FocusTrapOptions {
  /** Whether the trap is active */
  isActive: boolean
  /** Element to restore focus to on deactivate */
  restoreFocus?: boolean
  /** Initial element to focus on activate */
  initialFocus?: HTMLElement | (() => HTMLElement) | null
  /** Delay before focusing (ms) */
  focusDelay?: number
}

/**
 * Hook for trapping focus within a container
 *
 * @example
 * ```tsx
 * const modalRef = useRef<HTMLDivElement>(null)
 * useFocusTrap(modalRef, { isActive: isOpen })
 * ```
 */
export function useFocusTrap(
  containerRef: React.RefObject<HTMLElement>,
  options: FocusTrapOptions
) {
  const { isActive, restoreFocus = true, initialFocus, focusDelay = 50 } = options

  const previousActiveElement = useRef<HTMLElement | null>(null)
  const focusableElementsRef = useRef<HTMLElement[]>([])

  useEffect(() => {
    if (!isActive || !containerRef.current) return

    const container = containerRef.current

    // Store the currently focused element
    previousActiveElement.current = document.activeElement as HTMLElement

    // Collect focusable elements
    focusableElementsRef.current = getFocusableElements(container)

    // Determine initial focus target
    const getInitialFocus = (): HTMLElement => {
      if (initialFocus) {
        return typeof initialFocus === 'function' ? initialFocus() : initialFocus
      }
      const { first } = getFocusBoundaries(container)
      return first ?? container
    }

    // Focus the target after delay
    const focusTimer = setTimeout(() => {
      const target = getInitialFocus()
      target.focus()
    }, focusDelay)

    // Update focusable elements when DOM changes
    const updateFocusableElements = () => {
      if (containerRef.current) {
        focusableElementsRef.current = getFocusableElements(containerRef.current)
      }
    }

    const observer = new MutationObserver(updateFocusableElements)
    observer.observe(container, { childList: true, subtree: true })

    // Handle tab key for focus trap
    const handleTab = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return

      const focusable = focusableElementsRef.current
      if (focusable.length === 0) return

      const firstFocusable = focusable[0]
      const lastFocusable = focusable[focusable.length - 1]

      if (event.shiftKey && document.activeElement === firstFocusable) {
        event.preventDefault()
        lastFocusable.focus()
      } else if (!event.shiftKey && document.activeElement === lastFocusable) {
        event.preventDefault()
        firstFocusable.focus()
      }
    }

    document.addEventListener('keydown', handleTab)

    return () => {
      clearTimeout(focusTimer)
      document.removeEventListener('keydown', handleTab)
      observer.disconnect()

      // Restore focus to previous element
      if (restoreFocus && previousActiveElement.current) {
        previousActiveElement.current.focus()
      }
    }
  }, [isActive, containerRef, restoreFocus, initialFocus, focusDelay])

  // Return empty object - focusableElements is managed internally
  return {}
}

/**
 * Hook for managing focus return on unmount
 *
 * @example
 * ```tsx
 * const triggerRef = useRef<HTMLButtonElement>(null)
 * useFocusReturn(triggerRef, isOpen)
 * // When isOpen changes to false, focus returns to triggerRef
 * ```
 */
export function useFocusReturn(
  triggerRef: React.RefObject<HTMLElement>,
  isOpen: boolean
) {
  const wasOpen = useRef(false)

  useEffect(() => {
    if (!wasOpen.current && isOpen) {
      // Just opened
      wasOpen.current = true
    } else if (wasOpen.current && !isOpen) {
      // Just closed - restore focus
      triggerRef.current?.focus()
      wasOpen.current = false
    }
  }, [isOpen, triggerRef])
}

/**
 * Hook for auto-focusing an element on mount
 *
 * @example
 * ```tsx
 * const inputRef = useRef<HTMLInputElement>(null)
 * useAutoFocus(inputRef)
 * ```
 */
export function useAutoFocus(
  elementRef: React.RefObject<HTMLElement>,
  enabled: boolean = true,
  delay: number = 0
) {
  useEffect(() => {
    if (!enabled || !elementRef.current) return

    const timer = setTimeout(() => {
      elementRef.current?.focus()
    }, delay)

    return () => clearTimeout(timer)
  }, [enabled, elementRef, delay])
}
