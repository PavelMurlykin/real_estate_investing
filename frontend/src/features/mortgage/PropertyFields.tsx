import { useId } from 'react'

import type { CatalogOption } from '@/api/schemas'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'
import { NumberField } from '@/shared/ui/NumberField'

import type { ManualPropertyState } from './manualProperty'

export function PropertyFields({ value, onChange, errors }: {
  value: ManualPropertyState
  onChange: (value: ManualPropertyState) => void
  errors: Record<string, string>
}) {
  const identifier = useId()
  const update = (changes: Partial<ManualPropertyState>) => onChange({ ...value, ...changes })
  const context = (option?: CatalogOption) => option ? {
    regionLocationId: value.regionLocationId || String(option.regionLocationId ?? ''),
    districtLocationId: value.districtLocationId || String(option.districtLocationId ?? ''),
    localityId: value.localityId || String(option.localityId ?? ''),
    regionId: option.regionId === undefined ? value.regionId : String(option.regionId ?? ''),
    cityId: option.cityId === undefined ? value.cityId : String(option.cityId ?? ''),
    districtId: option.districtId === undefined ? value.districtId : String(option.districtId ?? ''),
    developerId: String(option.developerId ?? value.developerId),
  } : {}
  return (
    <div className="field-grid property-data-grid" aria-label="Данные объекта недвижимости">
      <RemoteSelect searchable dictionary="locations" label="Регион" value={value.regionLocationId ?? ''}
        filters={{ category: 'region' }}
        onChange={(regionLocationId) => update({ regionLocationId, regionId: '', districtLocationId: '', localityId: '', cityId: '', districtId: '', realEstateComplexId: '', buildingId: '' })} />
      <RemoteSelect searchable dictionary="locations" label="Населённый пункт" value={value.localityId ?? ''}
        filters={{ category: 'locality', regionId: value.regionLocationId }}
        onChange={(localityId, option) => update({ localityId, regionLocationId: value.regionLocationId || String(option?.regionId ?? ''), regionId: '', districtLocationId: '', cityId: '', districtId: '', realEstateComplexId: '', buildingId: '' })} />
      <RemoteSelect searchable dictionary="locations" label="Административный район" value={value.districtLocationId ?? ''}
        filters={{ category: 'district', regionId: value.regionLocationId, relatedToId: value.localityId }}
        onChange={(districtLocationId, option) => update({ districtLocationId, regionLocationId: value.regionLocationId || String(option?.regionId ?? ''), regionId: '', cityId: '', districtId: '', realEstateComplexId: '', buildingId: '' })} />
      <RemoteSelect searchable dictionary="developers" label="Застройщик" value={value.developerId}
        error={errors['manualProperty.developerId']}
        onChange={(developerId) => update({ developerId, realEstateComplexId: '', buildingId: '' })} />
      <RemoteSelect searchable dictionary="complexes" label="Жилой комплекс" value={value.realEstateComplexId}
        filters={{ regionLocationId: value.regionLocationId, districtLocationId: value.districtLocationId, localityId: value.localityId, developerId: value.developerId }}
        error={errors['manualProperty.realEstateComplexId']}
        onChange={(realEstateComplexId, option) => update({ ...context(option), realEstateComplexId, buildingId: '' })} />
      <RemoteSelect searchable dictionary="buildings" label="Корпус" value={value.buildingId}
        filters={{ realEstateComplexId: value.realEstateComplexId, regionLocationId: value.regionLocationId, districtLocationId: value.districtLocationId, localityId: value.localityId }} disabled={!value.realEstateComplexId}
        error={errors['manualProperty.buildingId']}
        onChange={(buildingId, option) => update({ ...context(option), buildingId })} />
      {([['apartmentNumber', 'Номер квартиры', 'text'], ['area', 'Площадь, м²', 'number'], ['floor', 'Этаж', 'number']] as const).map(([field, label, type]) => (
        type === 'number' ? <NumberField key={field} label={label} value={value[field]}
          min={field === 'area' ? '0.01' : '0'}
          increment={field === 'area' ? 0.01 : 1} step={field === 'area' ? '0.01' : '1'}
          onValueChange={(newValue) => update({
            [field]: newValue !== '' && Number(newValue) < (field === 'area' ? 0.01 : 0)
              ? (field === 'area' ? '0.01' : '0') : newValue,
          })}
          aria-invalid={Boolean(errors[`manualProperty.${field}`])}
          aria-describedby={errors[`manualProperty.${field}`] ? `${identifier}-${field}-error` : undefined}>
          {errors[`manualProperty.${field}`] ? <span className="field-error" id={`${identifier}-${field}-error`}>{errors[`manualProperty.${field}`]}</span> : null}
        </NumberField> : <div className="form-field" key={field}>
          <label htmlFor={`${identifier}-${field}`}>{label}</label>
          <input id={`${identifier}-${field}`} type={type} value={value[field]}
            onChange={(event) => update({ [field]: event.target.value })}
            aria-invalid={Boolean(errors[`manualProperty.${field}`])}
            aria-describedby={errors[`manualProperty.${field}`] ? `${identifier}-${field}-error` : undefined} />
          {errors[`manualProperty.${field}`] ? <span className="field-error" id={`${identifier}-${field}-error`}>{errors[`manualProperty.${field}`]}</span> : null}
        </div>
      ))}
      <RemoteSelect searchable dictionary="layouts" label="Планировка" value={value.layoutId}
        error={errors['manualProperty.layoutId']} onChange={(layoutId) => update({ layoutId })} />
      <RemoteSelect searchable dictionary="decorations" label="Отделка" value={value.decorationId}
        error={errors['manualProperty.decorationId']} onChange={(decorationId) => update({ decorationId })} />
    </div>
  )
}
