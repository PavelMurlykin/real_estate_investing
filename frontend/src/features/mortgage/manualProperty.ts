import type { ManualCalculationProperty, PropertyDetail, PropertyListItem } from '@/api/schemas'

type TerritoryField = 'regionLocationId' | 'districtLocationId' | 'localityId'

export type ManualPropertyState = Record<Exclude<keyof ManualCalculationProperty, TerritoryField>, string>
  & Partial<Record<TerritoryField | 'retainedRegionKey', string>>

export const emptyManualProperty: ManualPropertyState = {
  developerId: '', realEstateComplexId: '',
  buildingId: '', apartmentNumber: '', area: '', floor: '', layoutId: '', decorationId: '',
}

export function isManualPropertyComplete(value: ManualPropertyState | null): boolean {
  return value !== null && (Object.keys(emptyManualProperty) as (keyof ManualPropertyState)[])
    .every((field) => Boolean(value[field]?.trim()))
}

export function manualPropertyFromSelected(property?: PropertyListItem | PropertyDetail): ManualPropertyState {
  if (!property) return { ...emptyManualProperty }
  return {
    regionLocationId: String(property.regionLocationId ?? ''),
    districtLocationId: String(property.districtLocationId ?? ''),
    localityId: String(property.localityId ?? ''),
    retainedRegionKey: property.retainedRegionKey,
    developerId: String(property.developerId ?? ''),
    realEstateComplexId: String(property.realEstateComplexId ?? ''), buildingId: String(property.buildingId ?? ''),
    apartmentNumber: property.apartmentNumber, area: property.area, floor: String(property.floor),
    layoutId: String(property.layoutId ?? ''), decorationId: String(property.decorationId ?? ''),
  }
}

export function buildManualPropertyPayload(value: ManualPropertyState): ManualCalculationProperty {
  return {
    regionLocationId: value.regionLocationId ? Number(value.regionLocationId) : undefined,
    districtLocationId: value.districtLocationId ? Number(value.districtLocationId) : undefined,
    localityId: value.localityId ? Number(value.localityId) : undefined,
    developerId: Number(value.developerId), realEstateComplexId: Number(value.realEstateComplexId),
    buildingId: Number(value.buildingId), apartmentNumber: value.apartmentNumber,
    area: value.area, floor: Number(value.floor), layoutId: Number(value.layoutId),
    decorationId: Number(value.decorationId),
  }
}
