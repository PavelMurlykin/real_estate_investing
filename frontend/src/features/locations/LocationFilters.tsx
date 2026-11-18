import { useEffect } from 'react'
import { useLegacyLocation } from './useLegacyLocation'
import { useTableSearchParams } from '@/shared/lib/useTableSearchParams'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'

export function LocationFilters({ prefix = '' }: { prefix?: string }) {
  const [parameters, updateParameters] = useTableSearchParams()
  const parameterName = (name: string) => prefix ? `${prefix}${name[0].toUpperCase()}${name.slice(1)}` : name
  const region = parameters.get(parameterName('regionLocationId')) ?? ''
  const district = parameters.get(parameterName('districtLocationId')) ?? ''
  const legacyCity = parameters.get(parameterName('cityId')) ?? parameters.get(parameterName('city')) ?? ''
  const legacy = useLegacyLocation('legacyCityId', legacyCity)
  useEffect(() => {
    if (!legacyCity || !legacy.data) return
    const identifier = legacy.data.id
    updateParameters((next) => {
      const name = prefix ? `${prefix}LocalityId` : 'localityId'
      if (!next.has(name)) next.set(name, String(identifier))
      for (const field of ['city', 'cityId', 'page']) next.delete(prefix ? `${prefix}${field[0].toUpperCase()}${field.slice(1)}` : field)
    }, { replace: true })
  }, [legacyCity, legacy.data, updateParameters, prefix])
  const update = (field: string, value: string) => {
    updateParameters((next) => {
      if (value) next.set(parameterName(field), value)
      else next.delete(parameterName(field))
      if (field === 'regionLocationId') {
        next.delete(parameterName('districtLocationId')); next.delete(parameterName('localityId'))
      }
      if (field === 'districtLocationId') next.delete(parameterName('localityId'))
      for (const key of ['city', 'cityId', 'locationId', 'realEstateComplex', 'realEstateComplexId', 'building', 'buildingId', 'page']) next.delete(parameterName(key))
    })
  }
  return <>
    <RemoteSelect filter dictionary="locations" label="Регион" value={region}
      filters={{ category: 'region' }} onChange={(value) => update('regionLocationId', value)} />
    <RemoteSelect filter dictionary="locations" label="Административный район" value={district}
      filters={{ category: 'district', regionId: region }} onChange={(value) => update('districtLocationId', value)} />
    <RemoteSelect filter dictionary="locations" label="Населённый пункт" value={parameters.get(parameterName('localityId')) ?? ''}
      filters={{ category: 'locality', regionId: region, relatedToId: district }}
      onChange={(value) => update('localityId', value)} />
  </>
}
