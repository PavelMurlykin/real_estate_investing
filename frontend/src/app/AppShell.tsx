import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'

import { Sidebar } from './Sidebar'
import { useTheme } from './theme'
import { TopNavigation } from './TopNavigation'

export function AppShell() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const { theme, toggleTheme } = useTheme()

  useEffect(() => {
    if (!isSidebarOpen) {
      return undefined
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsSidebarOpen(false)
      }
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [isSidebarOpen])

  return (
    <div className="application-shell">
      <a className="skip-link" href="#main-content">Перейти к содержимому</a>
      <TopNavigation
        onOpenSidebar={() => setIsSidebarOpen(true)}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      <main id="main-content" className="main-content" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
