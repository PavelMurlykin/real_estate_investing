import type { ManualCalculationProperty, PropertyDetail, PropertyListItem } from '@/api/schemas'

export type ManualPropertyState = Record<keyof ManualCalculationProperty | 'regionId', string>

export const emptyManualProperty: ManualPropertyState = {
  regionId: '', cityId: '', districtId: '', developerId: '', realEstateComplexId: '',
  buildingId: '', apartmentNumber: '', area: '', floor: '', layoutId: '', decorationId: '',
}

export function manualPropertyFromSelected(property?: PropertyListItem | PropertyDetail): ManualPropertyState {
  if (!property) return { ...emptyManualProperty }
  return {
    regionId: String(property.regionId ?? ''), cityId: String(property.cityId ?? ''),
    districtId: String(property.districtId ?? ''), developerId: String(property.developerId ?? ''),
    realEstateComplexId: String(property.realEstateComplexId ?? ''), buildingId: String(property.buildingId ?? ''),
    apartmentNumber: property.apartmentNumber, area: property.area, floor: String(property.floor),
    layoutId: String(property.layoutId ?? ''), decorationId: String(property.decorationId ?? ''),
  }
}

export function buildManualPropertyPayload(value: ManualPropertyState): ManualCalculationProperty {
  return {
    cityId: Number(value.cityId), districtId: Number(value.districtId),
    developerId: Number(value.developerId), realEstateComplexId: Number(value.realEstateComplexId),
    buildingId: Number(value.buildingId), apartmentNumber: value.apartmentNumber,
    area: value.area, floor: Number(value.floor), layoutId: Number(value.layoutId),
    decorationId: Number(value.decorationId),
  }
}
