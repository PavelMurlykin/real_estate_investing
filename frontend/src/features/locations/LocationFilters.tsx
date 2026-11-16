import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { requestJson } from '@/api/client'
import { geographicPageSchema } from './geography'
import { useTableSearchParams } from '@/shared/lib/useTableSearchParams'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'

export function LocationFilters() {
  const [parameters, updateParameters] = useTableSearchParams()
  const region = parameters.get('regionLocationId') ?? ''
  const district = parameters.get('districtLocationId') ?? ''
  const legacyCity = parameters.get('cityId') ?? parameters.get('city') ?? ''
  const legacy = useQuery({ queryKey: ['legacy-location', legacyCity], enabled: Boolean(legacyCity),
    queryFn: ({ signal }) => requestJson(`/api/v1/locations/?legacyCityId=${encodeURIComponent(legacyCity)}`, geographicPageSchema, { signal }),
  })
  useEffect(() => {
    if (!legacyCity || !legacy.data?.results.length) return
    const identifier = legacy.data.results[0].id
    updateParameters((next) => {
      if (!next.has('localityId')) next.set('localityId', String(identifier))
      next.delete('city'); next.delete('cityId'); next.delete('page')
    }, { replace: true })
  }, [legacyCity, legacy.data, updateParameters])
  const update = (field: string, value: string) => {
    updateParameters((next) => {
      if (value) next.set(field, value)
      else next.delete(field)
      if (field === 'regionLocationId') {
        next.delete('districtLocationId'); next.delete('localityId')
      }
      if (field === 'districtLocationId') next.delete('localityId')
      for (const key of ['city', 'cityId', 'locationId', 'realEstateComplex', 'realEstateComplexId', 'building', 'buildingId', 'page']) next.delete(key)
    })
  }
  return <>
    <RemoteSelect filter dictionary="locations" label="Регион" value={region}
      filters={{ category: 'region' }} onChange={(value) => update('regionLocationId', value)} />
    <RemoteSelect filter dictionary="locations" label="Административный район" value={district}
      filters={{ category: 'district', regionId: region }} onChange={(value) => update('districtLocationId', value)} />
    <RemoteSelect filter dictionary="locations" label="Населённый пункт" value={parameters.get('localityId') ?? ''}
      filters={{ category: 'locality', regionId: region, relatedToId: district }}
      onChange={(value) => update('localityId', value)} />
  </>
}
