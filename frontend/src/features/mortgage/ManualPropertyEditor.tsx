import type { CatalogOption } from '@/api/schemas'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'

import type { ManualPropertyState } from './manualProperty'

export function ManualPropertyEditor({ value, onChange, errors }: {
  value: ManualPropertyState
  onChange: (value: ManualPropertyState) => void
  errors: Record<string, string>
}) {
  const update = (changes: Partial<ManualPropertyState>) => onChange({ ...value, ...changes })
  const context = (option?: CatalogOption) => option ? {
    regionId: String(option.regionId ?? value.regionId),
    cityId: String(option.cityId ?? value.cityId),
    districtId: String(option.districtId ?? value.districtId),
    developerId: String(option.developerId ?? value.developerId),
  } : {}
  return (
    <div className="field-grid property-data-grid" aria-label="Ручные данные объекта">
      <RemoteSelect dictionary="regions" label="Регион" value={value.regionId}
        onChange={(regionId) => update({ regionId, cityId: '', districtId: '', realEstateComplexId: '', buildingId: '' })} />
      <RemoteSelect dictionary="cities" label="Город" value={value.cityId} required
        filters={{ regionId: value.regionId }} error={errors['manualProperty.cityId']}
        onChange={(cityId, option) => update({ cityId, regionId: String(option?.regionId ?? ''), districtId: '', realEstateComplexId: '', buildingId: '' })} />
      <RemoteSelect dictionary="districts" label="Район" value={value.districtId} required
        filters={{ cityId: value.cityId }} disabled={!value.cityId} error={errors['manualProperty.districtId']}
        onChange={(districtId) => update({ districtId, realEstateComplexId: '', buildingId: '' })} />
      <RemoteSelect dictionary="developers" label="Застройщик" value={value.developerId} required
        error={errors['manualProperty.developerId']}
        onChange={(developerId) => update({ developerId, realEstateComplexId: '', buildingId: '' })} />
      <RemoteSelect dictionary="complexes" label="Жилой комплекс" value={value.realEstateComplexId} required
        filters={{ cityId: value.cityId, districtId: value.districtId, developerId: value.developerId }}
        error={errors['manualProperty.realEstateComplexId']}
        onChange={(realEstateComplexId, option) => update({ ...context(option), realEstateComplexId, buildingId: '' })} />
      <RemoteSelect dictionary="buildings" label="Корпус" value={value.buildingId} required
        filters={{ realEstateComplexId: value.realEstateComplexId }} disabled={!value.realEstateComplexId}
        error={errors['manualProperty.buildingId']}
        onChange={(buildingId) => update({ buildingId })} />
      {([['apartmentNumber', 'Номер квартиры', 'text'], ['area', 'Площадь, м²', 'number'], ['floor', 'Этаж', 'number']] as const).map(([field, label, type]) => (
        <label className="form-field" key={field}>
          <span>{label}</span>
          <input type={type} value={value[field]} required step={field === 'area' ? '0.01' : undefined}
            onChange={(event) => update({ [field]: event.target.value })}
            aria-invalid={Boolean(errors[`manualProperty.${field}`])} />
          {errors[`manualProperty.${field}`] ? <span className="field-error">{errors[`manualProperty.${field}`]}</span> : null}
        </label>
      ))}
      <RemoteSelect dictionary="layouts" label="Планировка" value={value.layoutId} required
        error={errors['manualProperty.layoutId']} onChange={(layoutId) => update({ layoutId })} />
      <RemoteSelect dictionary="decorations" label="Отделка" value={value.decorationId} required
        error={errors['manualProperty.decorationId']} onChange={(decorationId) => update({ decorationId })} />
    </div>
  )
}
