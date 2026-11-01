import type { AnchorHTMLAttributes } from 'react'

export function LegacyLink({ href, ...properties }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  const url = new URL(href, window.location.origin)
  if (url.origin === window.location.origin) url.searchParams.set('legacy', '1')
  const target = url.origin === window.location.origin
    ? `${url.pathname}${url.search}${url.hash}` : href
  return <a {...properties} href={target} />
}
