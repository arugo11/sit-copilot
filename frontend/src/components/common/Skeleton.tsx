/**
 * Skeleton Component
 * Based on docs/frontend.md Section 9.2
 */

import { cn } from '@/lib/utils'
import { prefersReducedMotion } from '@/lib/utils'
import { useTranslation } from 'react-i18next'

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'card' | 'table-row' | 'text' | 'circle'
}

export function Skeleton({ className, variant = 'text', ...props }: SkeletonProps) {
  const { t } = useTranslation()
  const variantClasses = {
    card: 'h-32 rounded-lg',
    'table-row': 'h-12 w-full',
    text: 'h-4 w-3/4',
    circle: 'h-12 w-12 rounded-full',
  }

  return (
    <div
      className={cn(
        !prefersReducedMotion() && 'animate-pulse',
        'bg-bg-muted rounded',
        variantClasses[variant],
        className
      )}
      role="status"
      aria-live="polite"
      aria-label={t('common.loading')}
      {...props}
    />
  )
}

/* Card Skeleton */
export function CardSkeleton() {
  return (
    <div className="card p-4 space-y-3">
      <Skeleton variant="circle" className="h-10 w-10" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  )
}

/* Table Row Skeleton */
export function TableRowSkeleton({ cells = 4 }: { cells?: number }) {
  return (
    <tr className="border-b border-border">
      {Array.from({ length: cells }).map((_, i) => (
        <td key={i} className="p-3">
          <Skeleton className="h-4 w-24" />
        </td>
      ))}
    </tr>
  )
}
