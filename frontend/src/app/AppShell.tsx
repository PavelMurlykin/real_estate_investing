import {
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { PageLoadingState } from '@/shared/ui/AsyncState'
import { controlLabel, LoadingFocusContext, type LoadingFocusTarget } from '@/shared/lib/loadingFocus'

import { PageErrorBoundary } from './PageErrorBoundary'
import { Sidebar } from './Sidebar'
import { useTheme } from './theme'
import { TopNavigation } from './TopNavigation'

// Keep this breakpoint aligned with the sidebar layout in styles.css.
const mobileSidebarQuery = '(max-width: 960px)'

function subscribeToViewport(onChange: () => void) {
  const mediaQuery = window.matchMedia(mobileSidebarQuery)
  mediaQuery.addEventListener('change', onChange)
  return () => mediaQuery.removeEventListener('change', onChange)
}

export function AppShell() {
  const location = useLocation()
  const [sidebarState, setSidebarState] = useState({
    locationKey: location.key,
    isOpen: false,
  })
  if (sidebarState.locationKey !== location.key) {
    setSidebarState({ locationKey: location.key, isOpen: false })
  }
  const isMobile = useSyncExternalStore(
    subscribeToViewport,
    () => window.matchMedia(mobileSidebarQuery).matches,
  )
  const isSidebarOpen = isMobile && sidebarState.locationKey === location.key
    && sidebarState.isOpen
  const closeSidebar = useCallback(() => {
    setSidebarState((current) => ({ ...current, isOpen: false }))
  }, [])
  const mainReference = useRef<HTMLElement>(null)
  const loadingFocus = useRef<LoadingFocusTarget | null>(null)
  const previousPathname = useRef(location.pathname)
  const { theme, cycleTheme } = useTheme()

  useEffect(() => {
    if (previousPathname.current !== location.pathname) {
      previousPathname.current = location.pathname
      mainReference.current?.focus({ preventScroll: true })
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
    }
  }, [location.pathname])

  useEffect(() => {
    const mediaQuery = window.matchMedia(mobileSidebarQuery)
    const closeOnDesktop = () => {
      if (!mediaQuery.matches) closeSidebar()
    }
    mediaQuery.addEventListener('change', closeOnDesktop)
    return () => mediaQuery.removeEventListener('change', closeOnDesktop)
  }, [closeSidebar])

  return (
    <LoadingFocusContext.Provider value={loadingFocus}>
      <div className="application-shell" onFocusCapture={(event) => {
        const element = event.target
        loadingFocus.current = { element, pathname: window.location.pathname, main: element.closest('main'), label: controlLabel(element) }
      }}>
        <a className="skip-link" href="#main-content">Перейти к содержимому</a>
        <TopNavigation
          onOpenSidebar={() => setSidebarState({ locationKey: location.key, isOpen: true })}
          isSidebarOpen={isSidebarOpen}
          theme={theme}
          onCycleTheme={cycleTheme}
        />
        <Sidebar isOpen={isSidebarOpen} isMobile={isMobile} onClose={closeSidebar} />
        <main ref={mainReference} id="main-content" className="main-content" tabIndex={-1}>
          <PageErrorBoundary key={location.pathname}>
            <Suspense fallback={<PageLoadingState />}>
              <Outlet />
            </Suspense>
          </PageErrorBoundary>
        </main>
      </div>
    </LoadingFocusContext.Provider>
  )
}
