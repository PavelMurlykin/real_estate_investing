import { useSearchParams } from 'react-router-dom'

import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'

export function PropertyFilters() {
  const [parameters, setParameters] = useSearchParams()
  const update = (name: string, value: string, dependents: string[] = []) => {
    const next = new URLSearchParams(parameters)
    if (value) next.set(name, value)
    else next.delete(name)
    dependents.forEach((field) => next.delete(field))
    next.delete('page')
    setParameters(next)
  }
  const select = (dictionary: string, label: string, name: string, dependents: string[] = [], filters = {}) => (
    <RemoteSelect filter dictionary={dictionary} label={label} value={parameters.get(name) ?? ''}
      initialOptions={[]} truncated filters={filters} onChange={(value) => update(name, value, dependents)} />
  )
  return (
    <div className="field-grid table-filters">
      {select('cities', 'Город', 'city', ['realEstateComplex', 'building'])}
      {select('developers', 'Застройщик', 'developer', ['realEstateComplex', 'building'])}
      {select('complexes', 'Жилой комплекс', 'realEstateComplex', ['building'], {
        cityId: parameters.get('city'), developerId: parameters.get('developer'),
      })}
      {select('buildings', 'Корпус', 'building', [], { realEstateComplexId: parameters.get('realEstateComplex') })}
      {select('layouts', 'Планировка', 'layout')}
      <LiveFilterInput label="Номер квартиры" parameter="apartmentNumber" />
      <LiveFilterInput label="Площадь, м²" parameter="area" type="number" max={99999999.99} />
      <LiveFilterInput label="Точная стоимость, ₽" parameter="propertyCost" type="number" max={9999999999999.99} />
    </div>
  )
}
