/**
 * TopBar Component
 * Sticky navigation bar with title and actions
 */

import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface TopBarProps {
  /** Page or section title */
  title: string
  /** Optional subtitle */
  subtitle?: string
  /** Action buttons/elements to display on the right */
  actions?: ReactNode[]
  /** Connection status indicator */
  connectionStatus?: 'connected' | 'disconnected' | 'connecting' | null
  /** Additional CSS classes */
  className?: string
}

export function TopBar({
  title,
  subtitle,
  actions = [],
  connectionStatus = null,
  className,
}: TopBarProps) {
  return (
    <div className={cn('flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between', className)}>
      {/* Left: Title and subtitle */}
      <div className="min-w-0 flex items-center gap-4">
        <div>
          <h1 className="text-xl font-semibold text-fg-primary">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-0.5 text-sm text-fg-secondary">
              {subtitle}
            </p>
          )}
        </div>
      </div>

      {/* Right: Actions and status */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Connection Status Pill */}
        {connectionStatus && (
          <ConnectionStatusPill status={connectionStatus} />
        )}

        {/* Action buttons */}
        {actions.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {actions.map((action, index) => (
              <div key={index}>
                {action}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

interface ConnectionStatusPillProps {
  status: 'connected' | 'disconnected' | 'connecting'
}

function ConnectionStatusPill({ status }: ConnectionStatusPillProps) {
  const statusConfig = {
    connected: {
      label: 'Connected',
      className: 'badge-success',
      dotColor: 'bg-success',
    },
    disconnected: {
      label: 'Disconnected',
      className: 'badge-danger',
      dotColor: 'bg-danger',
    },
    connecting: {
      label: 'Connecting...',
      className: 'badge-warning',
      dotColor: 'bg-warning',
    },
  }

  const config = statusConfig[status]

  return (
    <div
      className={cn(
        'badge gap-1.5',
        config.className
      )}
      role="status"
      aria-live="polite"
    >
      <span className={cn('h-2 w-2 rounded-full', config.dotColor)} />
      <span>{config.label}</span>
    </div>
  )
}
