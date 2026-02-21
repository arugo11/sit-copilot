/**
 * Modal Component
 * Dialog modal with focus trap, ESC to close, and scroll lock
 * WAI-ARIA compliant dialog
 */

import { useEffect, useRef, useCallback, useId } from 'react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface ModalProps {
  /** Whether the modal is open */
  isOpen: boolean
  /** Callback when modal should close */
  onClose: () => void
  /** Modal title */
  title: string
  /** Modal content */
  children: ReactNode
  /** Optional footer actions */
  footer?: ReactNode
  /** Size variant */
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  /** Additional CSS classes */
  className?: string
  /** When true, clicking overlay doesn't close */
  closeOnOverlayClick?: boolean
  /** When true, ESC key doesn't close */
  closeOnEscape?: boolean
}

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  className,
  closeOnOverlayClick = true,
  closeOnEscape = true,
}: ModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)
  const previousActiveElement = useRef<HTMLElement | null>(null)
  const focusableElementsRef = useRef<HTMLElement[]>([])
  const titleId = useId()

  // Size classes
  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    full: 'max-w-full mx-4',
  }

  // Handle background scroll lock
  useEffect(() => {
    if (isOpen) {
      // Store current scroll position
      const scrollY = window.scrollY

      // Lock body scroll
      document.body.style.overflow = 'hidden'
      document.body.style.position = 'fixed'
      document.body.style.top = `-${scrollY}px`
      document.body.style.width = '100%'

      return () => {
        // Restore scroll position
        const scrollY = document.body.style.top
        document.body.style.overflow = ''
        document.body.style.position = ''
        document.body.style.top = ''
        document.body.style.width = ''
        window.scrollTo(0, parseInt(scrollY || '0', 10) * -1)
      }
    }
  }, [isOpen])

  // Handle focus trap
  useEffect(() => {
    if (!isOpen) return

    // Store the previously focused element
    previousActiveElement.current = document.activeElement as HTMLElement

    // Focus the modal after a small delay to ensure it's rendered
    const focusTimer = setTimeout(() => {
      modalRef.current?.focus()
    }, 50)

    // Collect focusable elements
    const updateFocusableElements = () => {
      if (!modalRef.current) return
      focusableElementsRef.current = Array.from(
        modalRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      )
    }

    updateFocusableElements()

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

    // Mutation observer to update focusable elements when content changes
    const observer = new MutationObserver(updateFocusableElements)
    if (modalRef.current) {
      observer.observe(modalRef.current, { childList: true, subtree: true })
    }

    return () => {
      clearTimeout(focusTimer)
      document.removeEventListener('keydown', handleTab)
      observer.disconnect()
      // Restore focus to previous element
      previousActiveElement.current?.focus()
    }
  }, [isOpen])

  // Handle ESC key
  const handleEscape = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'Escape' && closeOnEscape) {
        onClose()
      }
    },
    [onClose, closeOnEscape]
  )

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      return () => document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen, handleEscape])

  // Don't render if not open
  if (!isOpen) return null

  const handleOverlayClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget && closeOnOverlayClick) {
      onClose()
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={handleOverlayClick}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-fg-primary/50 backdrop-blur-sm"
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cn(
          'relative bg-bg-surface rounded-lg shadow-xl border border-border',
          'max-h-[90vh] flex flex-col',
          'w-full',
          sizeClasses[size],
          className
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <h2
            id={titleId}
            className="text-lg font-semibold text-fg-primary"
          >
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="btn btn-ghost p-2 min-h-8 min-w-8"
            aria-label="Close dialog"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Body - scrollable if content is long */}
        <div className="flex-1 overflow-y-auto p-6">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 p-6 border-t border-border">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
