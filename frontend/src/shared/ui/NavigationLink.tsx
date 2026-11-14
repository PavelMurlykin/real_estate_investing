import type { MouseEventHandler, ReactNode } from 'react'
import { Link, matchPath, useLocation } from 'react-router-dom'

export type NavigationItem = {
  to: string
  label: string
  end?: boolean
  activePaths?: string[]
  excludedPaths?: string[]
}

export function NavigationLink({ to, label, end = false, activePaths, excludedPaths,
  icon, onNavigate, className = '' }: NavigationItem & { icon?: ReactNode; onNavigate?: MouseEventHandler<HTMLAnchorElement>; className?: string }) {
  const { pathname } = useLocation()
  const current = [to, ...activePaths ?? []].some((path) => matchPath({ path, end }, pathname))
    && !excludedPaths?.some((path) => matchPath({ path, end: false }, pathname))

  return <Link className={`navigation-link ${className}`} to={to} aria-current={current ? 'page' : undefined}
    onClick={(event) => {
      if (!event.defaultPrevented && event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) onNavigate?.(event)
    }}>
    {icon}<span>{label}</span>
  </Link>
}
