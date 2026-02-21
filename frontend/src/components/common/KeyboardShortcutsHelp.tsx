/**
 * KeyboardShortcutsHelp Component
 * Displays available keyboard shortcuts for accessibility
 * Based on docs/frontend.md Section 10.4
 */

import { cn } from '@/lib/utils'

export interface ShortcutItem {
  /** Key combination */
  keys: string[]
  /** Description of what the shortcut does */
  description: { ja: string; en: string }
  /** Category for grouping */
  category?: 'navigation' | 'action' | 'media' | 'accessibility'
}

export interface KeyboardShortcutsHelpProps {
  /** Array of keyboard shortcuts to display */
  shortcuts: ShortcutItem[]
  /** Current locale */
  locale?: 'ja' | 'en'
  /** Additional CSS classes */
  className?: string
  /** Optional title */
  title?: { ja: string; en: string }
  /** Whether to show categories */
  showCategories?: boolean
}

const categoryNames: Record<NonNullable<ShortcutItem['category']>, { ja: string; en: string }> = {
  navigation: { ja: 'ナビゲーション', en: 'Navigation' },
  action: { ja: '操作', en: 'Actions' },
  media: { ja: 'メディア', en: 'Media' },
  accessibility: { ja: 'アクセシビリティ', en: 'Accessibility' },
}

/**
 * Render a single key with proper styling
 */
function KeyBadge({ key: keyName }: { key: string }) {
  const displayKey = keyName === 'Control' ? 'Ctrl' : keyName === 'Escape' ? 'Esc' : keyName

  return (
    <kbd
      className={cn(
        'inline-flex items-center justify-center',
        'min-w-6 h-6 px-1.5',
        'bg-bg-muted border border-border rounded',
        'text-xs font-mono font-medium',
        'shadow-sm'
      )}
    >
      {displayKey.length === 1 ? displayKey.toUpperCase() : displayKey}
    </kbd>
  )
}

/**
 * Component for displaying keyboard shortcuts help
 */
export function KeyboardShortcutsHelp({
  shortcuts,
  locale = 'ja',
  className,
  title = { ja: 'キーボードショートカット', en: 'Keyboard Shortcuts' },
  showCategories = true,
}: KeyboardShortcutsHelpProps) {
  // Group shortcuts by category if enabled
  const groupedShortcuts = showCategories
    ? shortcuts.reduce<Record<string, ShortcutItem[]>>((acc, shortcut) => {
        const category = shortcut.category ?? 'action'
        if (!acc[category]) {
          acc[category] = []
        }
        acc[category].push(shortcut)
        return acc
      }, {})
    : { all: shortcuts }

  const categories = Object.keys(groupedShortcuts)

  return (
    <div
      className={cn('space-y-4', className)}
      role="region"
      aria-label={title[locale]}
    >
      <h3 className="text-sm font-semibold text-fg-primary">{title[locale]}</h3>

      <div className="space-y-4">
        {categories.map((category) => (
          <div key={category}>
            {showCategories && category !== 'all' && (
              <h4 className="text-xs font-medium text-fg-secondary mb-2">
                {categoryNames[category as keyof typeof categoryNames]?.[locale] ?? category}
              </h4>
            )}
            <dl className="space-y-2">
              {groupedShortcuts[category].map((shortcut, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between gap-4 py-1"
                >
                  <dt className="text-sm text-fg-primary">{shortcut.description[locale]}</dt>
                  <dd className="flex items-center gap-1" aria-hidden="true">
                    {shortcut.keys.map((key, keyIndex) => (
                      <span key={keyIndex} className="flex items-center gap-1">
                        {keyIndex > 0 && <span className="text-fg-secondary text-xs">+</span>}
                        <KeyBadge key={key} />
                      </span>
                    ))}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Quick keyboard shortcuts button that opens a modal with help
 */
export interface KeyboardShortcutButtonProps {
  /** Click handler */
  onClick: () => void
  /** Additional CSS classes */
  className?: string
  /** Locale */
  locale?: 'ja' | 'en'
}

export function KeyboardShortcutButton({ onClick, className, locale = 'ja' }: KeyboardShortcutButtonProps) {
  const label = locale === 'ja' ? 'キーボードショートカットを表示' : 'Show keyboard shortcuts'

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'btn btn-ghost',
        'text-xs',
        'flex items-center gap-2',
        className
      )}
      aria-label={label}
    >
      <svg
        className="w-4 h-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
        />
      </svg>
      <kbd
        className={cn(
          'hidden sm:inline-flex',
          'items-center justify-center',
          'min-w-5 h-5 px-1',
          'bg-bg-muted border border-border rounded',
          'text-xs font-mono'
        )}
        aria-hidden="true"
      >
        ?
      </kbd>
    </button>
  )
}
