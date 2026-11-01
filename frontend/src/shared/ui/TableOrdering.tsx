import { useId } from 'react'
import { useSearchParams } from 'react-router-dom'

type TableOrderingProps = {
  fields: { field: string; label: string }[]
  defaultOrdering: string
  id?: string
  parameter?: string
  pageParameter?: string
}

export function TableOrdering({ fields, defaultOrdering, id, parameter = 'ordering', pageParameter = 'page' }: TableOrderingProps) {
  const generatedIdentifier = useId()
  const identifier = id ?? generatedIdentifier
  const [parameters, setParameters] = useSearchParams()
  const current = parameters.get(parameter) ?? defaultOrdering
  return (
    <div className="sort-control">
      <label htmlFor={identifier}>Сортировка</label>
      <select id={identifier} value={current} onChange={(event) => {
        const next = new URLSearchParams(parameters)
        next.set(parameter, event.target.value)
        next.delete(pageParameter)
        setParameters(next)
      }}>
        {!fields.some(({ field }) => field === current.replace(/^-/, ''))
          ? <option value={current}>Исходный порядок</option> : null}
        {fields.flatMap(({ field, label }) => [
          <option key={field} value={field}>{label}: по возрастанию</option>,
          <option key={`-${field}`} value={`-${field}`}>{label}: по убыванию</option>,
        ])}
      </select>
    </div>
  )
}
