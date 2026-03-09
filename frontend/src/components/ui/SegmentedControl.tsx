/**
 * SegmentedControl Component
 * Tab-like control for mutually exclusive options
 * WAI-ARIA compliant with keyboard navigation
 */

import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface SegmentedOption<T = string> {
  value: T
  label: string
  icon?: ReactNode
  disabled?: boolean
}

export interface SegmentedControlProps<T = string> {
  /** Available options */
  options: SegmentedOption<T>[]
  /** Currently selected value */
  value: T
  /** Callback when selection changes */
  onChange: (value: T) => void
  /** Additional CSS classes */
  className?: string
  /** Optional aria label for the control */
  ariaLabel?: string
}

export function SegmentedControl<T extends string = string>({
  options,
  value,
  onChange,
  className,
  ariaLabel = 'Segmented control',
}: SegmentedControlProps<T>) {
  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    _index: number
  ) => {
    const enabledOptions = options.filter((opt) => !opt.disabled)
    const currentEnabledIndex = enabledOptions.findIndex(
      (opt) => opt.value === value
    )

    let nextIndex = currentEnabledIndex

    switch (event.key) {
      case 'ArrowLeft':
        event.preventDefault()
        nextIndex =
          currentEnabledIndex > 0
            ? currentEnabledIndex - 1
            : enabledOptions.length - 1
        break
      case 'ArrowRight':
        event.preventDefault()
        nextIndex =
          currentEnabledIndex < enabledOptions.length - 1
            ? currentEnabledIndex + 1
            : 0
        break
      case 'Home':
        event.preventDefault()
        nextIndex = 0
        break
      case 'End':
        event.preventDefault()
        nextIndex = enabledOptions.length - 1
        break
      default:
        return
    }

    if (nextIndex !== currentEnabledIndex) {
      onChange(enabledOptions[nextIndex].value)
      // Focus the newly selected button
      event.currentTarget
        .parentElement?.querySelectorAll<HTMLButtonElement>(
          '[role="tab"]'
        )
        [nextIndex]?.focus()
    }
  }

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn(
        'inline-flex max-w-full flex-wrap bg-bg-muted rounded-md p-1 gap-1',
        className
      )}
    >
      {options.map((option, index) => {
        const isSelected = option.value === value
        const isDisabled = option.disabled ?? false

        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={isSelected}
            aria-disabled={isDisabled}
            disabled={isDisabled}
            tabIndex={isSelected ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(e) => handleKeyDown(e, index as number)}
            className={cn(
              'inline-flex min-w-0 flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium sm:flex-none sm:px-4',
              'transition-all duration-180 ease-in-out',
              'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus',
              'min-h-[36px]',
              isSelected
                ? 'bg-bg-surface text-fg-primary shadow-sm'
                : 'text-fg-secondary hover:text-fg-primary hover:bg-bg-surface/50',
              isDisabled && 'opacity-50 cursor-not-allowed'
            )}
          >
            {option.icon && (
              <span className="flex-shrink-0" aria-hidden="true">
                {option.icon}
              </span>
            )}
            <span className="whitespace-normal text-center">{option.label}</span>
          </button>
        )
      })}
    </div>
  )
}
