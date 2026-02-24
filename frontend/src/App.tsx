/**
 * Main App Component
 */

import { useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from '@/components/common/Toast'
import { ThemeProvider } from '@/contexts'
import { useUserSettings } from '@/lib/api/hooks'
import i18n from '@/lib/i18n'
import { AppRouter } from './app/router'
import './lib/i18n'

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
})

function hasExplicitLanguageInLocalStorage(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  try {
    return Boolean(window.localStorage.getItem('i18nextLng'))
  } catch {
    return false
  }
}

function LanguagePreferenceBootstrap() {
  const { data: userSettings } = useUserSettings()

  useEffect(() => {
    if (hasExplicitLanguageInLocalStorage()) {
      return
    }

    const preferredLanguage = userSettings?.language
    if (preferredLanguage !== 'ja' && preferredLanguage !== 'en') {
      return
    }

    const currentLanguage =
      (i18n.resolvedLanguage ?? i18n.language).startsWith('en') ? 'en' : 'ja'
    if (currentLanguage === preferredLanguage) {
      return
    }

    void i18n.changeLanguage(preferredLanguage)
  }, [userSettings?.language])

  return null
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <LanguagePreferenceBootstrap />
          <AppRouter />
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default App
