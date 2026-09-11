import type { RealEstateComplexDetail } from '@/api/schemas'

export type BuildingFormRow = {
  clientIdentifier: string
  id?: number
  number: string
  address: string
  commissioningDate: string
  commissioningYear: string
  commissioningQuarter: string
  keyHandoverDate: string
  keyHandoverYear: string
  keyHandoverQuarter: string
  propertyCount: number
  isActive: boolean
}

export type MetroAvailabilityFormRow = {
  clientIdentifier: string
  id?: number
  metroId: string
  transportAccessibilityTypeId: string
  walkingTimeMinutes: string
  isActive: boolean
}

let nextClientIdentifier = 0

function createClientIdentifier(prefix: string) {
  nextClientIdentifier += 1
  return `${prefix}-${nextClientIdentifier}`
}

export function createEmptyBuildingRow(): BuildingFormRow {
  return {
    clientIdentifier: createClientIdentifier('building'),
    number: '',
    address: '',
    commissioningDate: '',
    commissioningYear: '',
    commissioningQuarter: '',
    keyHandoverDate: '',
    keyHandoverYear: '',
    keyHandoverQuarter: '',
    propertyCount: 0,
    isActive: true,
  }
}

export function createEmptyMetroRow(): MetroAvailabilityFormRow {
  return {
    clientIdentifier: createClientIdentifier('metro'),
    metroId: '',
    transportAccessibilityTypeId: '',
    walkingTimeMinutes: '',
    isActive: true,
  }
}

export function createBuildingRowsFromDetail(
  realEstateComplex: RealEstateComplexDetail,
): BuildingFormRow[] {
  return realEstateComplex.buildings.map((building) => ({
    clientIdentifier: createClientIdentifier('building'),
    id: building.id,
    number: building.number,
    address: building.address ?? '',
    commissioningDate: building.commissioningDate ?? '',
    commissioningYear: building.commissioningYear?.toString() ?? '',
    commissioningQuarter: building.commissioningQuarter?.toString() ?? '',
    keyHandoverDate: building.keyHandoverDate ?? '',
    keyHandoverYear: building.keyHandoverYear?.toString() ?? '',
    keyHandoverQuarter: building.keyHandoverQuarter?.toString() ?? '',
    propertyCount: building.propertyCount,
    isActive: building.isActive,
  }))
}

export function createMetroRowsFromDetail(
  realEstateComplex: RealEstateComplexDetail,
): MetroAvailabilityFormRow[] {
  return realEstateComplex.metroAvailability.map((availability) => ({
    clientIdentifier: createClientIdentifier('metro'),
    id: availability.id,
    metroId: availability.metroId.toString(),
    transportAccessibilityTypeId: (
      availability.transportAccessibilityTypeId.toString()
    ),
    walkingTimeMinutes: availability.walkingTimeMinutes.toString(),
    isActive: availability.isActive,
  }))
}
