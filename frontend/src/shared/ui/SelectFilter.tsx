import { useTableSearchParams } from '@/shared/lib/useTableSearchParams'
import { SearchableSelect, type SelectChoice } from './SearchableSelect'

type SelectFilterProps = {
  label: string
  parameter: string
  options: SelectChoice[]
  emptyLabel?: string
  pageParameter?: string
}

export function SelectFilter({ label, parameter, options, emptyLabel = 'Все', pageParameter = 'page' }: SelectFilterProps) {
  const [parameters, updateParameters] = useTableSearchParams()
  const value = parameters.get(parameter)
  return <SearchableSelect label={label} value={value === 'all' ? '' : value ?? ''} options={options} emptyLabel={emptyLabel}
    onChange={(value) => updateParameters((next) => {
      if (value) next.set(parameter, value)
      else next.delete(parameter)
      next.delete(pageParameter)
    })} />
}
