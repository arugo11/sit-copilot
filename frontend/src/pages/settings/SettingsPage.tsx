/**
 * Settings Page
 * Based on docs/frontend.md Section 8.6
 */

import { useEffect, useMemo, useState } from 'react'
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
  transcriptDensity: 'comfortable',
  autoScrollDefault: true,
}

function mergeWithDefaults(settings?: UserSettings): UserSettings {
  return { ...DEFAULT_SETTINGS, ...settings }
}

export function SettingsPage() {
  const { setTheme } = useTheme()
  const { showToast } = useToast()
  const { data: currentSettings, isLoading, error } = useUserSettings()
  const updateSettingsMutation = useUpdateSettings()

  const [initialSettings, setInitialSettings] = useState<UserSettings>(DEFAULT_SETTINGS)
  const [localChanges, setLocalChanges] = useState<Partial<UserSettings>>({})

  const effectiveSettings: UserSettings = useMemo(
    () => ({ ...mergeWithDefaults(currentSettings), ...localChanges }),
    [currentSettings, localChanges]
  )

  useEffect(() => {
    if (currentSettings) {
      const merged = mergeWithDefaults(currentSettings)
      setInitialSettings(merged)
      if (merged.theme) {
        setTheme(merged.theme as Theme)
      }
    }
  }, [currentSettings, setTheme])

  const hasChanges = Object.entries(localChanges).some(
    ([key, value]) => initialSettings[key as keyof UserSettings] !== value
  )

  const handleSettingChange = <K extends keyof UserSettings>(
    key: K,
    value: UserSettings[K]
  ) => {
    setLocalChanges((prev) => ({ ...prev, [key]: value }))
    if (key === 'theme' && typeof value === 'string') {
      setTheme(value as Theme)
    }
  }

  const handleSave = async () => {
    try {
      await updateSettingsMutation.mutateAsync({ settings: effectiveSettings })
      setLocalChanges({})
      setInitialSettings(effectiveSettings)
      showToast({ variant: 'success', title: '設定を保存しました' })
    } catch {
      // handled by hook
    }
  }

  const handleReset = () => {
    setLocalChanges({})
    setTheme((currentSettings?.theme ?? DEFAULT_SETTINGS.theme) as Theme)
  }

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
        <section className="card p-6 space-y-4">
          <h2 className="text-lg font-semibold">表示</h2>

          <div>
            <label className="block text-sm font-medium text-fg-primary mb-2" id="theme-label">
              テーマ
            </label>
            <div className="flex gap-2" role="radiogroup" aria-labelledby="theme-label" aria-label="テーマ選択">
              <button onClick={() => handleSettingChange('theme', 'light')} className={`btn ${effectiveSettings.theme === 'light' ? 'btn-primary' : 'btn-secondary'}`} role="radio" aria-checked={effectiveSettings.theme === 'light'}>
                ライト
              </button>
              <button onClick={() => handleSettingChange('theme', 'dark')} className={`btn ${effectiveSettings.theme === 'dark' ? 'btn-primary' : 'btn-secondary'}`} role="radio" aria-checked={effectiveSettings.theme === 'dark'}>
                ダーク
              </button>
              <button onClick={() => handleSettingChange('theme', 'high-contrast')} className={`btn ${effectiveSettings.theme === 'high-contrast' ? 'btn-primary' : 'btn-secondary'}`} role="radio" aria-checked={effectiveSettings.theme === 'high-contrast'}>
                ハイコントラスト
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-fg-primary mb-2">文字サイズ</label>
            <select className="input" value={effectiveSettings.fontSize || 'normal'} onChange={(e) => handleSettingChange('fontSize', e.target.value as UserSettings['fontSize'])}>
              <option value="small">小</option>
              <option value="normal">中</option>
              <option value="large">大</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-fg-primary mb-2">字幕密度</label>
            <select className="input" value={effectiveSettings.transcriptDensity || 'comfortable'} onChange={(e) => handleSettingChange('transcriptDensity', e.target.value as UserSettings['transcriptDensity'])}>
              <option value="comfortable">標準</option>
              <option value="compact">コンパクト</option>
            </select>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <label htmlFor="auto-scroll-default" className="text-sm font-medium text-fg-primary">
                自動スクロールを初期ONにする
              </label>
            </div>
            <input id="auto-scroll-default" type="checkbox" checked={effectiveSettings.autoScrollDefault ?? true} onChange={(e) => handleSettingChange('autoScrollDefault', e.target.checked)} className="w-5 h-5" />
          </div>
        </section>

        <section className="card p-6 space-y-4">
          <h2 className="text-lg font-semibold">言語</h2>
          <div>
            <label className="block text-sm font-medium text-fg-primary mb-2">UI言語</label>
            <select className="input" value={effectiveSettings.language || 'ja'} onChange={(e) => handleSettingChange('language', e.target.value as 'ja' | 'en')}>
              <option value="ja">日本語</option>
              <option value="en">English</option>
            </select>
          </div>
        </section>

        <section className="card p-6 space-y-4">
          <h2 className="text-lg font-semibold">アクセシビリティ</h2>
          <div className="flex items-center justify-between">
            <div>
              <label htmlFor="reduced-motion" className="text-sm font-medium text-fg-primary">アニメーションを減らす</label>
              <p className="text-xs text-fg-secondary">動きを最小限にして見やすくします</p>
            </div>
            <input id="reduced-motion" type="checkbox" checked={effectiveSettings.reducedMotion ?? false} onChange={(e) => handleSettingChange('reducedMotion', e.target.checked)} className="w-5 h-5" />
          </div>
        </section>

        <div className="flex justify-end gap-2">
          <button onClick={handleReset} className="btn btn-secondary" disabled={!hasChanges || updateSettingsMutation.isPending}>
            リセット
          </button>
          <button onClick={handleSave} className="btn btn-primary" disabled={!hasChanges || updateSettingsMutation.isPending}>
            {updateSettingsMutation.isPending ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}
