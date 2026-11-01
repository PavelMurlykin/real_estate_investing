import type { ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'

type SortableHeaderProps = {
  field: string
  children: ReactNode
  defaultOrdering?: string
  parameter?: string
  pageParameter?: string
}

export function SortableHeader({ field, children, defaultOrdering = 'name', parameter = 'ordering', pageParameter = 'page' }: SortableHeaderProps) {
  const [parameters, setParameters] = useSearchParams()
  const current = parameters.get(parameter) ?? defaultOrdering
  const active = current.replace(/^-/, '') === field
  const descending = active && current.startsWith('-')
  return (
    <th scope="col" aria-sort={active ? descending ? 'descending' : 'ascending' : 'none'}>
      <button type="button" className="sortable-header" onClick={() => {
        const next = new URLSearchParams(parameters)
        next.set(parameter, active && !descending ? `-${field}` : field)
        next.delete(pageParameter)
        setParameters(next)
      }}>
        <span>{children}</span><span aria-hidden="true">{active ? descending ? '↓' : '↑' : '↕'}</span>
      </button>
    </th>
  )
}
