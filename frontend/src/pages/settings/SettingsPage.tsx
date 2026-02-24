/**
 * Settings Page
 * Based on docs/frontend.md Section 8.6
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useTheme, type Theme } from '@/contexts'
import { useUserSettings, useUpdateSettings } from '@/lib/api/hooks'
import type { UserSettings } from '@/lib/api/client'
import { Skeleton } from '@/components/common/Skeleton'
import { EmptyState } from '@/components/common/EmptyState'
import { useToast } from '@/components/common/Toast'
import { useUiLanguagePreference } from '@/hooks/useUiLanguagePreference'

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
  const { t } = useTranslation()
  const { setTheme } = useTheme()
  const { showToast } = useToast()
  const { language, setLanguage, isPersisting } = useUiLanguagePreference()
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
      const nextSettings: UserSettings = {
        ...effectiveSettings,
        language,
      }
      await updateSettingsMutation.mutateAsync({ settings: nextSettings })
      setLocalChanges({})
      setInitialSettings(nextSettings)
      showToast({ variant: 'success', title: t('settings.messages.saved') })
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
        <h1 className="text-2xl font-bold text-fg-primary mb-6">{t('settings.title')}</h1>
        <EmptyState
          variant="error"
          title={t('settings.messages.loadFailedTitle')}
          description={error.message || t('settings.messages.loadFailedDescription')}
        />
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-2xl">
        <h1 className="text-2xl font-bold text-fg-primary mb-6">{t('settings.title')}</h1>
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
      <h1 className="text-2xl font-bold text-fg-primary mb-6">{t('settings.title')}</h1>

      <div className="space-y-6">
        <section className="card p-6 space-y-4">
          <h2 className="text-lg font-semibold">{t('settings.sections.display')}</h2>

          <div>
            <label className="block text-sm font-medium text-fg-primary mb-2" id="theme-label">
              {t('settings.theme.title')}
            </label>
            <div className="flex gap-2" role="radiogroup" aria-labelledby="theme-label" aria-label={t('settings.theme.ariaLabel')}>
              <button onClick={() => handleSettingChange('theme', 'light')} className={`btn ${effectiveSettings.theme === 'light' ? 'btn-primary' : 'btn-secondary'}`} role="radio" aria-checked={effectiveSettings.theme === 'light'}>
                {t('settings.theme.light')}
              </button>
              <button onClick={() => handleSettingChange('theme', 'dark')} className={`btn ${effectiveSettings.theme === 'dark' ? 'btn-primary' : 'btn-secondary'}`} role="radio" aria-checked={effectiveSettings.theme === 'dark'}>
                {t('settings.theme.dark')}
              </button>
              <button onClick={() => handleSettingChange('theme', 'high-contrast')} className={`btn ${effectiveSettings.theme === 'high-contrast' ? 'btn-primary' : 'btn-secondary'}`} role="radio" aria-checked={effectiveSettings.theme === 'high-contrast'}>
                {t('settings.theme.highContrast')}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-fg-primary mb-2">{t('settings.fontSize.title')}</label>
            <select className="input" value={effectiveSettings.fontSize || 'normal'} onChange={(e) => handleSettingChange('fontSize', e.target.value as UserSettings['fontSize'])}>
              <option value="small">{t('settings.fontSize.small')}</option>
              <option value="normal">{t('settings.fontSize.normal')}</option>
              <option value="large">{t('settings.fontSize.large')}</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-fg-primary mb-2">{t('settings.transcriptDensity.title')}</label>
            <select className="input" value={effectiveSettings.transcriptDensity || 'comfortable'} onChange={(e) => handleSettingChange('transcriptDensity', e.target.value as UserSettings['transcriptDensity'])}>
              <option value="comfortable">{t('settings.transcriptDensity.comfortable')}</option>
              <option value="compact">{t('settings.transcriptDensity.compact')}</option>
            </select>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <label htmlFor="auto-scroll-default" className="text-sm font-medium text-fg-primary">
                {t('settings.transcriptDensity.autoScrollDefault')}
              </label>
            </div>
            <input id="auto-scroll-default" type="checkbox" checked={effectiveSettings.autoScrollDefault ?? true} onChange={(e) => handleSettingChange('autoScrollDefault', e.target.checked)} className="w-5 h-5" />
          </div>
        </section>

        <section className="card p-6 space-y-4">
          <h2 className="text-lg font-semibold">{t('settings.sections.language')}</h2>
          <div>
            <label className="block text-sm font-medium text-fg-primary mb-2">{t('settings.language.title')}</label>
            <select
              className="input"
              value={language}
              onChange={(event) => {
                const next = event.target.value === 'en' ? 'en' : 'ja'
                void setLanguage(next)
              }}
              aria-busy={isPersisting}
            >
              <option value="ja">{t('landing.languageSelector.options.ja')}</option>
              <option value="en">{t('landing.languageSelector.options.en')}</option>
            </select>
            <p className="text-xs text-fg-secondary mt-2">
              {isPersisting
                ? t('landing.languageSelector.saving')
                : t('settings.language.description')}
            </p>
          </div>
        </section>

        <section className="card p-6 space-y-4">
          <h2 className="text-lg font-semibold">{t('settings.sections.accessibility')}</h2>
          <div className="flex items-center justify-between">
            <div>
              <label htmlFor="reduced-motion" className="text-sm font-medium text-fg-primary">{t('settings.accessibility.reducedMotion')}</label>
              <p className="text-xs text-fg-secondary">{t('settings.accessibility.reducedMotionDesc')}</p>
            </div>
            <input id="reduced-motion" type="checkbox" checked={effectiveSettings.reducedMotion ?? false} onChange={(e) => handleSettingChange('reducedMotion', e.target.checked)} className="w-5 h-5" />
          </div>
        </section>

        <div className="flex justify-end gap-2">
          <button onClick={handleReset} className="btn btn-secondary" disabled={!hasChanges || updateSettingsMutation.isPending}>
            {t('settings.actions.reset')}
          </button>
          <button onClick={handleSave} className="btn btn-primary" disabled={!hasChanges || updateSettingsMutation.isPending}>
            {updateSettingsMutation.isPending
              ? t('settings.actions.saving')
              : t('settings.actions.save')}
          </button>
        </div>
      </div>
    </div>
  )
}
