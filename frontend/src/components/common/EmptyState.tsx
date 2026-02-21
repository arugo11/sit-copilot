/**
 * EmptyState Component
 * Based on docs/frontend.md Section 9.2
 */

import type { ReactNode } from 'react'

interface EmptyStateProps {
  variant?: 'no-data' | 'no-results' | 'error' | 'permission'
  title: string
  description?: string
  action?: ReactNode
  icon?: ReactNode
}

export function EmptyState({
  variant = 'no-data',
  title,
  description,
  action,
  icon,
}: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center p-12 text-center"
      role={variant === 'error' ? 'alert' : 'status'}
      aria-live={variant === 'error' ? 'assertive' : 'polite'}
    >
      {icon && (
        <div className="mb-4 text-fg-secondary" aria-hidden="true">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-semibold text-fg-primary mb-2">
        {title}
      </h3>
      {description && (
        <p className="text-sm text-fg-secondary max-w-md mb-4">
          {description}
        </p>
      )}
      {action && (
        <div className="mt-4">
          {action}
        </div>
      )}
    </div>
  )
}
