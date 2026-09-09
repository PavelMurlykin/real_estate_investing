import { NavLink } from 'react-router-dom'

type TopNavigationProps = {
  onOpenSidebar: () => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}

export function TopNavigation({
  onOpenSidebar,
  theme,
  onToggleTheme,
}: TopNavigationProps) {
  return (
    <header className="topbar">
      <button
        className="icon-button topbar__menu-button"
        type="button"
        aria-label="Открыть меню разделов"
        aria-controls="application-sidebar"
        onClick={onOpenSidebar}
      >
        <span aria-hidden="true">☰</span>
      </button>

      <div className="brand" aria-label="RealtyFlow">
        <span className="brand__mark" aria-hidden="true">R</span>
        <span className="brand__name">RealtyFlow</span>
      </div>

      <nav className="top-navigation" aria-label="Основная навигация">
        <NavLink to="/" end>
          Главная
        </NavLink>
        <NavLink to="/properties">Объекты недвижимости</NavLink>
        <NavLink to="/mortgage">Ипотечный калькулятор</NavLink>
      </nav>

      <button
        className="icon-button theme-toggle"
        type="button"
        aria-label={theme === 'light' ? 'Включить тёмную тему' : 'Включить светлую тему'}
        onClick={onToggleTheme}
      >
        <span aria-hidden="true">{theme === 'light' ? '☾' : '☀'}</span>
      </button>
    </header>
  )
}
