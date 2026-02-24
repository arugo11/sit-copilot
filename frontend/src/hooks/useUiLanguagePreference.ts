import { useCallback, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useToast } from '@/components/common/Toast'
import { settingsApi, type UserSettings } from '@/lib/api/client'
import { queryKeys, useUserSettings } from '@/lib/api/hooks'

export type UiLanguage = 'ja' | 'en'

function normalizeLanguage(value: string | undefined): UiLanguage {
  return value?.startsWith('en') ? 'en' : 'ja'
}

function getPersistenceErrorCopy(language: UiLanguage): {
  title: string
  message: string
} {
  if (language === 'en') {
    return {
      title: 'Could not save language preference',
      message: 'The selected language is still applied locally.',
    }
  }
  return {
    title: '言語設定を保存できませんでした',
    message: '選択した言語はローカル表示に反映されています。',
  }
}

export function useUiLanguagePreference(): {
  language: UiLanguage
  setLanguage: (next: UiLanguage) => Promise<void>
  isPersisting: boolean
} {
  const { i18n } = useTranslation()
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const { data: userSettings } = useUserSettings()
  const [isPersisting, setIsPersisting] = useState(false)

  const language = normalizeLanguage(i18n.resolvedLanguage ?? i18n.language)

  const setLanguage = useCallback(
    async (next: UiLanguage) => {
      const current = normalizeLanguage(i18n.resolvedLanguage ?? i18n.language)
      if (current === next && userSettings?.language === next) {
        return
      }

      await i18n.changeLanguage(next)
      setIsPersisting(true)

      try {
        let baseSettings: UserSettings | undefined =
          userSettings ??
          queryClient.getQueryData<UserSettings>(queryKeys.settings.me)

        if (!baseSettings) {
          try {
            baseSettings = await settingsApi.get()
            queryClient.setQueryData(queryKeys.settings.me, baseSettings)
          } catch {
            baseSettings = {}
          }
        }

        const mergedSettings: UserSettings = {
          ...(baseSettings ?? {}),
          language: next,
        }
        const updated = await settingsApi.update(mergedSettings)
        queryClient.setQueryData(queryKeys.settings.me, updated)
      } catch {
        const copy = getPersistenceErrorCopy(next)
        showToast({
          variant: 'warning',
          title: copy.title,
          message: copy.message,
        })
      } finally {
        setIsPersisting(false)
      }
    },
    [i18n, queryClient, showToast, userSettings]
  )

  return {
    language,
    setLanguage,
    isPersisting,
  }
}
