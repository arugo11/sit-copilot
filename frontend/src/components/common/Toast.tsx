/**
 * Toast Component
 * Based on docs/frontend.md Section 9.2 and 10.5
 * Enhanced with live region announcements
 */

import { createContext, useContext, useState, useCallback } from 'react'
import type { ReactNode } from 'react'

type ToastVariant = 'success' | 'warning' | 'danger' | 'info'

interface Toast {
  id: string
  variant: ToastVariant
  title: string
  message?: string
  duration?: number
}

interface ToastContextValue {
  toasts: Toast[]
  showToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined)

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return context
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const announceToScreenReader = useCallback((message: string, priority: 'polite' | 'assertive') => {
    // Create or find live region
    let liveRegion = document.getElementById('toast-live-region')
    if (!liveRegion) {
      liveRegion = document.createElement('div')
      liveRegion.id = 'toast-live-region'
      liveRegion.setAttribute('aria-atomic', 'true')
      liveRegion.className = 'sr-only'
      document.body.appendChild(liveRegion)
    }

    // Update aria-live before each announcement
    liveRegion.setAttribute('aria-live', priority)

    // Announce the message
    liveRegion.textContent = ''
    setTimeout(() => {
      liveRegion!.textContent = message
    }, 0)
  }, [])

  const showToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).substring(2, 9)
    const newToast = { ...toast, id }

    setToasts((prev) => [...prev, newToast])

    // Announce to screen readers
    const message = toast.message ? `${toast.title}: ${toast.message}` : toast.title
    const priority = toast.variant === 'danger' ? 'assertive' : 'polite'
    announceToScreenReader(message, priority)

    // Auto-dismiss
    const duration = toast.duration ?? 5000
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, duration)
  }, [announceToScreenReader])

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, showToast, removeToast }}>
      {children}
      <ToastContainer />
    </ToastContext.Provider>
  )
}

function ToastContainer() {
  const { toasts, removeToast } = useToast()

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2"
      role="region"
      aria-live="off" // We handle announcements manually
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={removeToast} />
      ))}
    </div>
  )
}

const variantIconPaths: Record<ToastVariant, string> = {
  success: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  warning: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
  danger: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z',
  info: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
}

const variantClasses: Record<ToastVariant, { container: string; icon: string }> = {
  success: {
    container: 'badge-success border-success/20',
    icon: 'text-success',
  },
  warning: {
    container: 'badge-warning border-warning/20',
    icon: 'text-warning',
  },
  danger: {
    container: 'badge-danger border-danger/20',
    icon: 'text-danger',
  },
  info: {
    container: 'bg-bg-muted text-fg-primary border-border',
    icon: 'text-accent',
  },
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: string) => void }) {
  const classes = variantClasses[toast.variant]

  return (
    <div
      className={cn(
        'card p-4 min-w-80 max-w-md shadow-lg border',
        'flex items-start gap-3',
        classes.container
      )}
      role="alert"
      aria-live={toast.variant === 'danger' ? 'assertive' : 'polite'}
      aria-atomic="true"
    >
      {/* Status icon */}
      <svg
        className={cn('w-5 h-5 flex-shrink-0 mt-0.5', classes.icon)}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d={variantIconPaths[toast.variant]}
        />
      </svg>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <h4 className="font-semibold text-sm mb-0.5">{toast.title}</h4>
        {toast.message && (
          <p className="text-sm opacity-90 break-words">{toast.message}</p>
        )}
      </div>

      {/* Close button */}
      <button
        onClick={() => onDismiss(toast.id)}
        className={cn(
          'flex-shrink-0 p-1 rounded',
          'text-fg-secondary hover:text-fg-primary hover:bg-bg-muted',
          'focus:outline-2 focus:outline-offset-2 focus:outline-focus'
        )}
        aria-label="Close notification"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}

/* Utility function */
function cn(...classes: (string | boolean | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}
