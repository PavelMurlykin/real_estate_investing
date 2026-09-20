import { useEffect, useState } from 'react'

export type ThemePreference = 'system' | 'light' | 'dark'
type ResolvedTheme = Exclude<ThemePreference, 'system'>

const themeStorageKey = 'theme-preference'
const colorSchemeQuery = '(prefers-color-scheme: dark)'

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia?.(colorSchemeQuery).matches
    ? 'dark'
    : 'light'
}

function getInitialTheme(): ThemePreference {
  try {
    const storedTheme = window.localStorage.getItem(themeStorageKey)
    if (
      storedTheme === 'system'
      || storedTheme === 'light'
      || storedTheme === 'dark'
    ) {
      return storedTheme
    }
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts.
  }
  return 'system'
}

export function useTheme() {
  const [theme, setTheme] = useState<ThemePreference>(getInitialTheme)
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(getSystemTheme)
  const resolvedTheme = theme === 'system' ? systemTheme : theme

  useEffect(() => {
    const mediaQuery = window.matchMedia(colorSchemeQuery)
    const handleSystemThemeChange = (event: MediaQueryListEvent) => {
      setSystemTheme(event.matches ? 'dark' : 'light')
    }
    mediaQuery.addEventListener('change', handleSystemThemeChange)
    return () => mediaQuery.removeEventListener('change', handleSystemThemeChange)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme
    document.documentElement.style.colorScheme = resolvedTheme
    try {
      window.localStorage.setItem(themeStorageKey, theme)
    } catch {
      // The selected theme still applies for this page when storage is blocked.
    }
  }, [resolvedTheme, theme])

  return {
    theme,
    resolvedTheme,
    cycleTheme: () => setTheme((current) => {
      if (current === 'system') return 'light'
      if (current === 'light') return 'dark'
      return 'system'
    }),
  }
}
