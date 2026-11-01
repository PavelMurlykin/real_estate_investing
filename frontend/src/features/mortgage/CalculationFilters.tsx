import { useSearchParams } from 'react-router-dom'

import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'
import { calculationRanges } from './calculationFilterFields'

export function CalculationFilters({ prefix = '' }: { prefix?: string }) {
  const [parameters, setParameters] = useSearchParams()
  const parameterName = (name: string) => prefix ? `${prefix}${name[0].toUpperCase()}${name.slice(1)}` : name
  const pageParameter = parameterName('page')
  const cityParameter = parameterName('city')
  return (
    <div className="field-grid table-filters">
      <RemoteSelect dictionary="cities" label="Город расчёта" value={parameters.get(cityParameter) ?? ''}
        initialOptions={[]} truncated
        onChange={(value) => {
          const next = new URLSearchParams(parameters)
          if (value) next.set(cityParameter, value)
          else next.delete(cityParameter)
          next.delete(pageParameter)
          setParameters(next)
        }} />
      {calculationRanges.map(([name, label]) => (
        <fieldset className="filter-range" key={name}>
          <legend>{label}</legend>
          <LiveFilterInput label={`${label}: от`} parameter={parameterName(`${name}From`)} pageParameter={pageParameter}
            caption="От"
            type="number" max={name === 'term' ? 50 : name === 'rate' ? 100 : 9999999999999.99} />
          <LiveFilterInput label={`${label}: до`} parameter={parameterName(`${name}To`)} pageParameter={pageParameter}
            caption="До"
            type="number" max={name === 'term' ? 50 : name === 'rate' ? 100 : 9999999999999.99} />
        </fieldset>
      ))}
    </div>
  )
}
