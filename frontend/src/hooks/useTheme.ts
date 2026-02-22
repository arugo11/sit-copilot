/**
 * useTheme hook
 * Manages light/dark/high-contrast theme via data-theme attribute
 * Persisted in localStorage
 */
import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark' | 'high-contrast'

const STORAGE_KEY = 'sit_copilot_theme'

function getSystemPreference(): Theme {
    if (typeof window === 'undefined') return 'light'
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function loadTheme(): Theme {
    try {
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored === 'dark' || stored === 'light' || stored === 'high-contrast') {
            return stored
        }
    } catch {
        // ignore
    }
    return getSystemPreference()
}

function applyTheme(theme: Theme): void {
    document.documentElement.dataset.theme = theme
}

export function useTheme() {
    const [theme, setThemeState] = useState<Theme>(() => {
        const t = loadTheme()
        applyTheme(t)
        return t
    })

    useEffect(() => {
        applyTheme(theme)
        try {
            localStorage.setItem(STORAGE_KEY, theme)
        } catch {
            // ignore
        }
    }, [theme])

    const setTheme = useCallback((next: Theme) => {
        setThemeState(next)
    }, [])

    const toggleTheme = useCallback(() => {
        setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'))
    }, [])

    return { theme, setTheme, toggleTheme }
}
