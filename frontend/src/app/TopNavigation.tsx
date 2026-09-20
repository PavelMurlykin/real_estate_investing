import { NavLink } from 'react-router-dom'

import type { ThemePreference } from './theme'

type TopNavigationProps = {
  onOpenSidebar: () => void
  isSidebarOpen?: boolean
  theme: ThemePreference
  onCycleTheme: () => void
}

const themeLabels: Record<ThemePreference, string> = {
  system: 'системная',
  light: 'светлая',
  dark: 'тёмная',
}

const nextThemeLabels: Record<ThemePreference, string> = {
  system: 'светлую',
  light: 'тёмную',
  dark: 'системную',
}

function ThemeIcon({ theme }: { theme: ThemePreference }) {
  if (theme === 'system') {
    return (
      <svg className="theme-toggle__icon" viewBox="0 0 24 24" aria-hidden="true">
        <rect x="3" y="4" width="18" height="13" rx="2" />
        <path d="M8 21h8M12 17v4" />
      </svg>
    )
  }
  if (theme === 'light') {
    return (
      <svg className="theme-toggle__icon" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
      </svg>
    )
  }
  return (
    <svg className="theme-toggle__icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20.6 15.6A9 9 0 0 1 8.4 3.4 9 9 0 1 0 20.6 15.6Z" />
    </svg>
  )
}

export function TopNavigation({
  onOpenSidebar,
  isSidebarOpen = false,
  theme,
  onCycleTheme,
}: TopNavigationProps) {
  const themeControlLabel = `Тема: ${themeLabels[theme]}. Включить ${nextThemeLabels[theme]} тему`

  return (
    <header className="topbar">
      <button
        className="icon-button topbar__menu-button"
        type="button"
        aria-label="Открыть меню разделов"
        aria-controls="application-sidebar"
        aria-expanded={isSidebarOpen}
        aria-haspopup="dialog"
        onClick={onOpenSidebar}
      >
        <span aria-hidden="true">☰</span>
      </button>

      <NavLink className="brand" to="/" end aria-label="RealtyFlow — на главную">
        <span className="brand__mark" aria-hidden="true">R</span>
        <span className="brand__name">RealtyFlow</span>
      </NavLink>

      <nav className="top-navigation" aria-label="Основная навигация">
        <NavLink to="/properties">Объекты недвижимости</NavLink>
        <NavLink to="/mortgage">Ипотечный калькулятор</NavLink>
      </nav>

      <button
        className="icon-button theme-toggle"
        type="button"
        aria-label={themeControlLabel}
        title={themeControlLabel}
        onClick={onCycleTheme}
      >
        <ThemeIcon theme={theme} />
      </button>
    </header>
  )
}
