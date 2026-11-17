import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { LocationFilters } from '@/features/locations/LocationFilters'
import { calculationRanges } from './calculationFilterFields'

export function CalculationFilters({ prefix = '' }: { prefix?: string }) {
  const parameterName = (name: string) => prefix ? `${prefix}${name[0].toUpperCase()}${name.slice(1)}` : name
  const pageParameter = parameterName('page')
  return (
    <div className="field-grid table-filters">
      <LocationFilters prefix={prefix} />
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
