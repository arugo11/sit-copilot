/**
 * Tabs Component
 * Content tabs with WAI-ARIA compliance and keyboard navigation
 * Supports arrow keys, Home, End, and activation
 */

import { useState } from 'react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface TabProps {
  /** Unique identifier for the tab */
  value: string
  /** Display label for the tab */
  label: string
  /** Optional icon */
  icon?: ReactNode
  /** Content to display when tab is active */
  content: ReactNode
  /** Disable the tab */
  disabled?: boolean
}

export interface TabsProps {
  /** Tab definitions */
  tabs: TabProps[]
  /** Initially active tab value */
  defaultTab: string
  /** Optional controlled active tab value */
  activeTab?: string
  /** Callback when tab changes */
  onChange?: (value: string) => void
  /** Additional CSS classes for the container */
  className?: string
}

export function Tabs({
  tabs,
  defaultTab,
  activeTab: controlledTab,
  onChange,
  className,
}: TabsProps) {
  const [internalTab, setInternalTab] = useState(defaultTab)

  const activeTab = controlledTab ?? internalTab

  const setActiveTab = (value: string) => {
    if (value === activeTab) return
    if (controlledTab === undefined) {
      setInternalTab(value)
    }
    onChange?.(value)
  }

  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    _currentIndex: number
  ) => {
    const enabledTabs = tabs.filter((tab) => !tab.disabled)
    const currentEnabledIndex = enabledTabs.findIndex(
      (tab) => tab.value === activeTab
    )

    let nextIndex = currentEnabledIndex

    switch (event.key) {
      case 'ArrowLeft':
        event.preventDefault()
        nextIndex =
          currentEnabledIndex > 0
            ? currentEnabledIndex - 1
            : enabledTabs.length - 1
        break
      case 'ArrowRight':
        event.preventDefault()
        nextIndex =
          currentEnabledIndex < enabledTabs.length - 1
            ? currentEnabledIndex + 1
            : 0
        break
      case 'Home':
        event.preventDefault()
        nextIndex = 0
        break
      case 'End':
        event.preventDefault()
        nextIndex = enabledTabs.length - 1
        break
      default:
        return
    }

    if (nextIndex !== currentEnabledIndex) {
      setActiveTab(enabledTabs[nextIndex].value)
      // Focus the newly selected tab
      event.currentTarget
        .parentElement?.querySelectorAll<HTMLButtonElement>(
          '[role="tab"]'
        )
        [nextIndex]?.focus()
    }
  }

  const activeTabData = tabs.find((tab) => tab.value === activeTab)

  return (
    <div className={cn('w-full', className)}>
      {/* Tab List */}
      <div
        role="tablist"
        aria-label="Content tabs"
        className="border-b border-border"
      >
        <div className="-mb-px flex flex-wrap gap-1 sm:flex-nowrap">
          {tabs.map((tab, index) => {
            const isActive = tab.value === activeTab
            const isDisabled = tab.disabled ?? false

            return (
              <button
                key={tab.value}
                type="button"
                role="tab"
                id={`tab-${tab.value}`}
                aria-selected={isActive}
                aria-controls={`panel-${tab.value}`}
                aria-disabled={isDisabled}
                disabled={isDisabled}
                tabIndex={isActive ? 0 : -1}
                onClick={() => setActiveTab(tab.value)}
                onKeyDown={(e) => handleKeyDown(e, index as number)}
                className={cn(
                  'inline-flex min-w-0 items-center justify-center gap-2 rounded-t-md border-b-2 px-3 py-3 text-sm font-medium sm:px-4',
                  'transition-colors duration-180 ease-in-out',
                  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus',
                  'min-h-[44px]',
                  'flex-1 sm:flex-none',
                  isActive
                    ? 'border-accent text-accent'
                    : 'border-transparent text-fg-secondary hover:text-fg-primary hover:border-fg-secondary/30',
                  isDisabled && 'opacity-50 cursor-not-allowed hover:border-transparent hover:text-fg-secondary'
                )}
              >
                {tab.icon && (
                  <span className="flex-shrink-0" aria-hidden="true">
                    {tab.icon}
                  </span>
                )}
                <span className="whitespace-normal text-center">{tab.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Tab Panels */}
      <div className="mt-4">
        {activeTabData && (
          <div
            role="tabpanel"
            id={`panel-${activeTabData.value}`}
            aria-labelledby={`tab-${activeTabData.value}`}
            tabIndex={0}
          >
            {activeTabData.content}
          </div>
        )}
      </div>
    </div>
  )
}
