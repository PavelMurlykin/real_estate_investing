import type { ReactNode } from 'react'

type TableScrollAreaProps = {
  label: string
  children: ReactNode
  className?: string
}

export function TableScrollArea({ label, children, className = 'property-table-wrapper' }: TableScrollAreaProps) {
  return <div className={`table-scroll-area ${className}`} role="region" aria-label={`Прокрутка: ${label}`} tabIndex={0}
    onFocus={(event) => {
      if (event.target === event.currentTarget) event.currentTarget.scrollIntoView?.({ block: 'start', inline: 'nearest' })
    }}>
    {children}
  </div>
}
