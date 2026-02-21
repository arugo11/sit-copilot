/**
 * Theme Context
 * Provides theme state and switching functionality across the app.
 * Theme preference persists in localStorage.
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type Theme = 'light' | 'dark' | 'high-contrast'

interface ThemeContextValue {
  theme: Theme
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

const THEME_STORAGE_KEY = 'app-theme'
const DEFAULT_THEME: Theme = 'light'

interface ThemeProviderProps {
  children: ReactNode
}

/**
 * ThemeProvider Component
 * Manages theme state and applies theme to document.documentElement via data-theme attribute.
 * Theme preference is persisted in localStorage for future sessions.
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(() => {
    // Initialize from localStorage or use default
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (stored && isValidTheme(stored)) {
      return stored as Theme
    }
    return DEFAULT_THEME
  })

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme)
    localStorage.setItem(THEME_STORAGE_KEY, newTheme)
  }

  useEffect(() => {
    // Apply theme to document element
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const value: ThemeContextValue = {
    theme,
    setTheme,
  }

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

/**
 * useTheme Hook
 * Consumes the ThemeContext.
 * Throws error if used outside ThemeProvider.
 *
 * @example
 * const { theme, setTheme } = useTheme()
 * setTheme('dark')
 */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

/**
 * Type guard for Theme validation
 */
function isValidTheme(value: string): value is Theme {
  return ['light', 'dark', 'high-contrast'].includes(value)
}
