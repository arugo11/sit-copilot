/**
 * Settings Page
 * Based on docs/frontend.md Section 8.6
 */

import { useState, useRef, useEffect } from 'react'
import { useTheme, type Theme } from '@/contexts'
import { useUserSettings, useUpdateSettings } from '@/lib/api/hooks'
import type { UserSettings } from '@/lib/api/client'
import { Skeleton } from '@/components/common/Skeleton'
import { EmptyState } from '@/components/common/EmptyState'
import { useToast } from '@/components/common/Toast'

const DEFAULT_SETTINGS: UserSettings = {
  theme: 'light',
  language: 'ja',
  fontSize: 'normal',
  reducedMotion: false,
}

// Helper to merge settings with defaults
function mergeWithDefaults(settings?: UserSettings): UserSettings {
  return { ...DEFAULT_SETTINGS, ...settings }
}

export function SettingsPage() {
  const { setTheme } = useTheme()
  const { showToast } = useToast()

  // Fetch current settings from API
  const { data: currentSettings, isLoading, error } = useUserSettings()
  const updateSettingsMutation = useUpdateSettings()

  // Ref to track initial settings for comparison
  const initialSettingsRef = useRef<UserSettings>(DEFAULT_SETTINGS)

  // Local state for form changes
  const [localChanges, setLocalChanges] = useState<Partial<UserSettings>>({})

  // Computed settings: defaults + API data + local changes
  const effectiveSettings: UserSettings = {
    ...mergeWithDefaults(currentSettings),
    ...localChanges,
  }

  // Track initial settings when API data changes
  useEffect(() => {
    if (currentSettings) {
      initialSettingsRef.current = mergeWithDefaults(currentSettings)
      // Sync theme with ThemeContext if API has theme preference
      if (currentSettings.theme) {
        setTheme(currentSettings.theme as Theme)
      }
    }
  }, [currentSettings, setTheme])

  // Check if there are unsaved changes (compare actual values, not just keys)
  const hasChanges = Object.keys(localChanges).length > 0 &&
    Object.entries(localChanges).some(([key, value]) =>
      initialSettingsRef.current[key as keyof UserSettings] !== value
    )

  const handleSettingChange = <K extends keyof UserSettings>(
    key: K,
    value: UserSettings[K]
  ) => {
    setLocalChanges((prev) => ({ ...prev, [key]: value }))

    // Update theme immediately for better UX
    if (key === 'theme' && typeof value === 'string') {
      setTheme(value as Theme)
    }
  }

  const handleSave = async () => {
    try {
      // Save the full settings (API data + local changes)
      await updateSettingsMutation.mutateAsync({ settings: effectiveSettings })
      setLocalChanges({})
      // Update initial settings reference after successful save
      initialSettingsRef.current = effectiveSettings
      showToast({
        variant: 'success',
        title: '設定を保存しました',
      })
    } catch {
      // Error is handled by the mutation hook
    }
  }

  const handleReset = async () => {
    setLocalChanges({})
    // Reset theme to API value
    const themeToSet = currentSettings?.theme ?? DEFAULT_SETTINGS.theme
    setTheme(themeToSet as Theme)
  }

  // Show error state
  if (error) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-2xl">
        <h1 className="text-2xl font-bold text-fg-primary mb-6">設定</h1>
        <EmptyState
          variant="error"
          title="設定の読み込みに失敗しました"
          description={error.message || 'ネットワーク接続を確認してください'}
        />
      </div>
    )
  }

  // Show loading state
  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-2xl">
        <h1 className="text-2xl font-bold text-fg-primary mb-6">設定</h1>
        <div className="space-y-6">
          <div className="card p-6 space-y-4">
            <Skeleton className="h-6 w-20" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-10 w-40" />
          </div>
          <div className="card p-6 space-y-4">
            <Skeleton className="h-6 w-16" />
            <Skeleton className="h-4 w-full" />
          </div>
          <div className="card p-6 space-y-4">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-full" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-fg-primary mb-6">設定</h1>

      <div className="space-y-6">
        {/* Display Settings */}
        <section className="card p-6 space-y-4">
          <h2 className="text-lg font-semibold">表示</h2>

          {/* Theme */}
          <div>
            <label className="block text-sm font-medium text-fg-primary mb-2" id="theme-label">
              テーマ
            </label>
            <div
              className="flex gap-2"
              role="radiogroup"
              aria-labelledby="theme-label"
              aria-label="テーマ選択"
            >
              <button
                onClick={() => handleSettingChange('theme', 'light')}
                className={`btn ${effectiveSettings.theme === 'light' ? 'btn-primary' : 'btn-secondary'}`}
                role="radio"
                aria-checked={effectiveSettings.theme === 'light'}
              >
                ライト
              </button>
              <button
                onClick={() => handleSettingChange('theme', 'dark')}
                className={`btn ${effectiveSettings.theme === 'dark' ? 'btn-primary' : 'btn-secondary'}`}
                role="radio"
                aria-checked={effectiveSettings.theme === 'dark'}
              >
                ダーク
              </button>
              <button
                onClick={() => handleSettingChange('theme', 'high-contrast')}
                className={`btn ${effectiveSettings.theme === 'high-contrast' ? 'btn-primary' : 'btn-secondary'}`}
                role="radio"
                aria-checked={effectiveSettings.theme === 'high-contrast'}
              >
                ハイコントラスト
              </button>
            </div>
          </div>

          {/* Font Size */}
          <div>
            <label className="block text-sm font-medium text-fg-primary mb-2">
              文字サイズ
            </label>
            <select
              className="input"
              value={effectiveSettings.fontSize || 'normal'}
              onChange={(e) => handleSettingChange('fontSize', e.target.value as UserSettings['fontSize'])}
            >
              <option value="small">小</option>
              <option value="normal">中</option>
              <option value="large">大</option>
            </select>
          </div>
        </section>

        {/* Language Settings */}
        <section className="card p-6 space-y-4">
          <h2 className="text-lg font-semibold">言語</h2>

          <div>
            <label className="block text-sm font-medium text-fg-primary mb-2">
              UI言語
            </label>
            <select
              className="input"
              value={effectiveSettings.language || 'ja'}
              onChange={(e) => handleSettingChange('language', e.target.value as 'ja' | 'en')}
            >
              <option value="ja">日本語</option>
              <option value="en">English</option>
            </select>
          </div>
        </section>

        {/* Accessibility Settings */}
        <section className="card p-6 space-y-4">
          <h2 className="text-lg font-semibold">アクセシビリティ</h2>

          <div className="flex items-center justify-between">
            <div>
              <label htmlFor="reduced-motion" className="text-sm font-medium text-fg-primary">
                アニメーションを減らす
              </label>
              <p className="text-xs text-fg-secondary">
                動きを最小限にして見やすくします
              </p>
            </div>
            <input
              id="reduced-motion"
              type="checkbox"
              checked={effectiveSettings.reducedMotion ?? false}
              onChange={(e) => handleSettingChange('reducedMotion', e.target.checked)}
              className="w-5 h-5"
            />
          </div>
        </section>

        {/* Save Button */}
        <div className="flex justify-end gap-2">
          <button
            onClick={handleReset}
            className="btn btn-secondary"
            disabled={!hasChanges || updateSettingsMutation.isPending}
          >
            リセット
          </button>
          <button
            onClick={handleSave}
            className="btn btn-primary"
            disabled={!hasChanges || updateSettingsMutation.isPending}
          >
            {updateSettingsMutation.isPending ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}
