import { useSearchParams } from 'react-router-dom'

/** Reset a list without discarding the customer or surrounding page context. */
export function ResetFilters({ prefix }: { prefix?: string }) {
  const [parameters, setParameters] = useSearchParams()
  return <div className="filter-actions"><button type="button" className="button button--secondary" onClick={() => {
    const next = new URLSearchParams(parameters)
    for (const name of [...next.keys()]) {
      if (prefix ? name.startsWith(prefix) : name !== 'customerId') next.delete(name)
    }
    setParameters(next)
  }}>Сбросить</button></div>
}
