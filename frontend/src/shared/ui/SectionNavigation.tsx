import { useEffect, useRef, type KeyboardEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { NavigationLink, type NavigationItem } from './NavigationLink'

function revealLink(container: HTMLElement, link: HTMLElement | null) {
  if (!link) return
  const bounds = container.getBoundingClientRect()
  const item = link.getBoundingClientRect()
  if (item.left < bounds.left + 4) container.scrollLeft += item.left - bounds.left - 4
  else if (item.right > bounds.right - 4) container.scrollLeft += item.right - bounds.right + 4
}

/** Route links retain native Tab/Enter behavior and offer optional arrow navigation. */
export function SectionNavigation({ label, items, className = 'dictionary-tabs' }: {
  label: string; items: NavigationItem[]; className?: string
}) {
  const reference = useRef<HTMLElement>(null)
  const { pathname } = useLocation()
  useEffect(() => {
    const revealCurrent = () => {
      const container = reference.current
      if (container) revealLink(container, container.querySelector('[aria-current="page"]'))
    }
    revealCurrent()
    window.addEventListener('resize', revealCurrent)
    return () => window.removeEventListener('resize', revealCurrent)
  }, [pathname])

  const moveFocus = (event: KeyboardEvent<HTMLElement>) => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    const links = [...event.currentTarget.querySelectorAll<HTMLAnchorElement>('a[href]')]
    const index = links.indexOf(event.target as HTMLAnchorElement)
    if (index < 0) return
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? links.length - 1
      : (index + (event.key === 'ArrowRight' ? 1 : -1) + links.length) % links.length
    event.preventDefault()
    links[next]?.focus()
    revealLink(event.currentTarget, links[next])
  }

  return <nav ref={reference} className={className} aria-label={label} onKeyDown={moveFocus}
    onFocusCapture={(event) => revealLink(event.currentTarget, (event.target as HTMLElement).closest('a'))}>
    {items.map((item) => <NavigationLink key={item.to} {...item} />)}
  </nav>
}
