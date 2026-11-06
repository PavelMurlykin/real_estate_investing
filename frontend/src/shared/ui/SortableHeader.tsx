import type { ReactNode } from 'react'

import { useTableSearchParams } from '@/shared/lib/useTableSearchParams'

type SortableHeaderProps = {
  field: string
  children: ReactNode
  defaultOrdering?: string
  parameter?: string
  pageParameter?: string
}

export function SortableHeader({ field, children, defaultOrdering = 'name', parameter = 'ordering', pageParameter = 'page' }: SortableHeaderProps) {
  const [parameters, updateParameters] = useTableSearchParams()
  const current = parameters.get(parameter) ?? defaultOrdering
  const active = current.replace(/^-/, '') === field
  const descending = active && current.startsWith('-')
  return (
    <th scope="col" aria-sort={active ? descending ? 'descending' : 'ascending' : 'none'}>
      <button type="button" className="sortable-header" onClick={() => updateParameters((next) => {
        const currentOrdering = next.get(parameter) ?? defaultOrdering
        next.set(parameter, currentOrdering === field ? `-${field}` : field)
        next.delete(pageParameter)
      })}>
        <span>{children}</span><span aria-hidden="true">{active ? descending ? '↓' : '↑' : '↕'}</span>
      </button>
    </th>
  )
}
