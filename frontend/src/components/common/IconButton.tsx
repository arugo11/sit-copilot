/**
 * IconButton Component
 * Accessible icon-only button with proper aria-label
 * Based on docs/frontend.md Section 9.1 and 10.3
 */

import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  /** Icon to display */
  icon: ReactNode
  /** Accessible label (required for icon-only buttons) */
  'aria-label': string
  /** Optional description for additional context */
  'aria-describedby'?: string
  /** Button variant */
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  /** Button size */
  size?: 'sm' | 'md' | 'lg'
  /** Whether the button is disabled */
  disabled?: boolean
  /** Additional CSS classes */
  className?: string
}

const sizeClasses = {
  sm: 'min-h-8 min-w-8 p-1.5',
  md: 'min-h-10 min-w-10 p-2',
  lg: 'min-h-12 min-w-12 p-2.5',
}

const variantClasses = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
  danger: 'bg-danger text-white hover:opacity-90',
}

/**
 * Accessible icon-only button component
 *
 * @example
 * ```tsx
 * <IconButton
 *   icon={<CloseIcon />}
 *   aria-label="Close dialog"
 *   onClick={onClose}
 * />
 * ```
 */
export function IconButton({
  icon,
  'aria-label': ariaLabel,
  'aria-describedby': ariaDescribedby,
  variant = 'ghost',
  size = 'md',
  disabled = false,
  className,
  type = 'button',
  ...props
}: IconButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-describedby={ariaDescribedby}
      className={cn(
        'btn',
        'inline-flex items-center justify-center',
        'rounded-md',
        'transition-all duration-180 ease-in-out',
        variantClasses[variant],
        sizeClasses[size],
        disabled && 'cursor-not-allowed opacity-50',
        className
      )}
      {...props}
    >
      <span className="flex items-center justify-center" aria-hidden="true">
        {icon}
      </span>
    </button>
  )
}

/**
 * Icon button with tooltip for additional context
 */
export interface IconButtonWithTooltipProps extends IconButtonProps {
  /** Tooltip text (should match aria-label for consistency) */
  tooltip: string
  /** Tooltip position */
  tooltipPosition?: 'top' | 'bottom' | 'left' | 'right'
}

export function IconButtonWithTooltip({
  tooltip,
  ...props
}: IconButtonWithTooltipProps) {
  return (
    <div className="relative inline-flex">
      <IconButton {...props} />
      <span
        className={cn(
          'absolute pointer-events-none',
          'px-2 py-1',
          'bg-fg-primary text-bg-surface',
          'text-xs whitespace-nowrap rounded',
          'opacity-0 group-hover:opacity-100',
          'transition-opacity duration-200',
          'sr-only' // Hidden by default, can be shown via CSS on hover
        )}
        role="tooltip"
      >
        {tooltip}
      </span>
    </div>
  )
}

/**
 * Button with icon and text
 */
export interface IconTextButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  /** Icon to display (before text) */
  icon?: ReactNode
  /** Icon to display (after text) */
  iconAfter?: ReactNode
  /** Button text */
  children: ReactNode
  /** Optional aria-label if different from children text */
  'aria-label'?: string
  /** Button variant */
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  /** Button size */
  size?: 'sm' | 'md' | 'lg'
  /** Additional CSS classes */
  className?: string
}

export function IconTextButton({
  icon,
  iconAfter,
  children,
  'aria-label': ariaLabel,
  variant = 'primary',
  size = 'md',
  className,
  type = 'button',
  ...props
}: IconTextButtonProps) {
  return (
    <button
      type={type}
      aria-label={ariaLabel}
      className={cn(
        'btn',
        'inline-flex items-center justify-center gap-2',
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
      {...props}
    >
      {icon && <span aria-hidden="true">{icon}</span>}
      <span>{children}</span>
      {iconAfter && <span aria-hidden="true">{iconAfter}</span>}
    </button>
  )
}
