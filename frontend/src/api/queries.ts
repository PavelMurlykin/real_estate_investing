import { queryOptions } from '@tanstack/react-query'

import { requestFile, requestJson, requestWithoutResponse } from './client'
import {
  bankDetailSchema,
  bankListResponseSchema,
  bankOptionsSchema,
  companyGroupListResponseSchema,
  companyGroupSchema,
  customerCalculationLinkResponseSchema,
  customerCalculationListResponseSchema,
  customerDetailSchema,
  customerFormOptionsSchema,
  customerListResponseSchema,
  customerMutationResponseSchema,
  developerListResponseSchema,
  developerRegistryImportSummarySchema,
  developerMortgageProgramImportResultSchema,
  developerMortgageProgramListResponseSchema,
  developerMortgageProgramOptionsSchema,
  developerMortgageProgramSchema,
  developerOptionsSchema,
  developerSchema,
  keyRateListResponseSchema,
  keyRateSyncResultSchema,
  locationDictionaryEntrySchema,
  locationDictionaryListResponseSchema,
  locationDictionaryOptionsSchema,
  mortgageCalculationResponseSchema,
  mortgageOptionsSchema,
  mortgageProgramDetailSchema,
  mortgageProgramListResponseSchema,
  mortgageProgramOptionsSchema,
  overviewSchema,
  propertyDetailSchema,
  propertyDictionaryEntrySchema,
  propertyDictionaryListResponseSchema,
  propertyFormOptionsSchema,
  propertyListResponseSchema,
  realEstateComplexDetailSchema,
  realEstateComplexListResponseSchema,
  realEstateComplexOptionsSchema,
  savedMortgageCalculationDetailSchema,
  savedMortgageCalculationListResponseSchema,
  savedTrenchMortgageCalculationCreateResponseSchema,
  savedTrenchMortgageCalculationDetailSchema,
  savedTrenchMortgageCalculationListResponseSchema,
  sessionSchema,
  trenchMortgageCalculationResponseSchema,
} from './schemas'
import type {
  BankWriteRequest,
  CustomerCalculationLinkCreateRequest,
  CustomerCalculationSelection,
  CustomerCalculationProgramType,
  CustomerWriteRequest,
  DeveloperMortgageProgramWriteRequest,
  DeveloperWriteRequest,
  LoginRequest,
  LocationDictionaryKey,
  LocationDictionaryWriteRequest,
  MortgageCalculationRequest,
  MortgageProgramWriteRequest,
  PropertyDictionaryKey,
  PropertyDictionaryWriteRequest,
  SavedMortgageCalculationCreateRequest,
  SavedTrenchMortgageCalculationCreateRequest,
  TrenchMortgageCalculationRequest,
} from './schemas'

export const sessionQueryOptions = queryOptions({
  queryKey: ['session'],
  queryFn: ({ signal }) =>
    requestJson('/api/v1/auth/session/', sessionSchema, { signal }),
  staleTime: 60_000,
})

export function loginUser(payload: LoginRequest) {
  return requestJson('/api/v1/auth/login/', sessionSchema, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export const overviewQueryOptions = queryOptions({
  queryKey: ['overview'],
  queryFn: ({ signal }) =>
    requestJson('/api/v1/overview/', overviewSchema, { signal }),
  staleTime: 60_000,
})

export function bankListQueryOptions(searchParameters: URLSearchParams) {
  const normalizedParameters = new URLSearchParams()
  for (const fieldName of [
    'q',
    'scope',
    'status',
    'ordering',
    'page',
    'pageSize',
  ]) {
    const value = searchParameters.get(fieldName)
    if (value) normalizedParameters.set(fieldName, value)
  }
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['banks', queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/banks/${queryString ? `?${queryString}` : ''}`,
      bankListResponseSchema,
      { signal },
    ),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  })
}

export function bankDetailQueryOptions(bankIdentifier: number) {
  return queryOptions({
    queryKey: ['bank', bankIdentifier],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/banks/${bankIdentifier}/`,
      bankDetailSchema,
      { signal },
    ),
    staleTime: 60_000,
  })
}

export const bankOptionsQueryOptions = queryOptions({
  queryKey: ['bank-options'],
  queryFn: ({ signal }) => requestJson(
    '/api/v1/banks/options/',
    bankOptionsSchema,
    { signal },
  ),
  staleTime: 5 * 60_000,
})

export function createBank(payload: BankWriteRequest) {
  return requestJson('/api/v1/banks/', bankDetailSchema, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateBank(
  bankIdentifier: number,
  payload: BankWriteRequest,
) {
  return requestJson(`/api/v1/banks/${bankIdentifier}/`, bankDetailSchema, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteBank(bankIdentifier: number) {
  return requestWithoutResponse(`/api/v1/banks/${bankIdentifier}/`, {
    method: 'DELETE',
  })
}

export function mortgageProgramListQueryOptions(
  searchParameters: URLSearchParams,
) {
  const normalizedParameters = new URLSearchParams()
  for (const fieldName of [
    'q',
    'programType',
    'status',
    'ordering',
    'page',
    'pageSize',
  ]) {
    const value = searchParameters.get(fieldName)
    if (value) normalizedParameters.set(fieldName, value)
  }
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['mortgage-programs', queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/mortgage-programs/${queryString ? `?${queryString}` : ''}`,
      mortgageProgramListResponseSchema,
      { signal },
    ),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  })
}

export function mortgageProgramDetailQueryOptions(
  mortgageProgramIdentifier: number,
) {
  return queryOptions({
    queryKey: ['mortgage-program', mortgageProgramIdentifier],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/mortgage-programs/${mortgageProgramIdentifier}/`,
      mortgageProgramDetailSchema,
      { signal },
    ),
    staleTime: 60_000,
  })
}

export const mortgageProgramOptionsQueryOptions = queryOptions({
  queryKey: ['mortgage-program-options'],
  queryFn: ({ signal }) => requestJson(
    '/api/v1/mortgage-programs/options/',
    mortgageProgramOptionsSchema,
    { signal },
  ),
  staleTime: 5 * 60_000,
})

export function createMortgageProgram(payload: MortgageProgramWriteRequest) {
  return requestJson(
    '/api/v1/mortgage-programs/',
    mortgageProgramDetailSchema,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function updateMortgageProgram(
  mortgageProgramIdentifier: number,
  payload: MortgageProgramWriteRequest,
) {
  return requestJson(
    `/api/v1/mortgage-programs/${mortgageProgramIdentifier}/`,
    mortgageProgramDetailSchema,
    { method: 'PATCH', body: JSON.stringify(payload) },
  )
}

export function deleteMortgageProgram(mortgageProgramIdentifier: number) {
  return requestWithoutResponse(
    `/api/v1/mortgage-programs/${mortgageProgramIdentifier}/`,
    { method: 'DELETE' },
  )
}

export function developerMortgageProgramListQueryOptions(
  searchParameters: URLSearchParams,
) {
  const normalizedParameters = new URLSearchParams()
  for (const fieldName of [
    'q',
    'companyGroupId',
    'realEstateComplexId',
    'bankId',
    'mortgageProgramId',
    'status',
    'ordering',
    'page',
    'pageSize',
  ]) {
    const value = searchParameters.get(fieldName)
    if (value) normalizedParameters.set(fieldName, value)
  }
  const queryString = normalizedParameters.toString()
  return queryOptions({
    queryKey: ['developer-mortgage-programs', queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/developer-mortgage-programs/${queryString ? `?${queryString}` : ''}`,
      developerMortgageProgramListResponseSchema,
      { signal },
    ),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  })
}

export function developerMortgageProgramDetailQueryOptions(
  developerProgramIdentifier: number,
) {
  return queryOptions({
    queryKey: ['developer-mortgage-program', developerProgramIdentifier],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/developer-mortgage-programs/${developerProgramIdentifier}/`,
      developerMortgageProgramSchema,
      { signal },
    ),
    staleTime: 60_000,
  })
}

export function developerMortgageProgramOptionsQueryOptions(
  companyGroupIdentifier: number | null,
) {
  const queryString = companyGroupIdentifier
    ? `?companyGroupId=${companyGroupIdentifier}`
    : ''
  return queryOptions({
    queryKey: ['developer-mortgage-program-options', companyGroupIdentifier],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/developer-mortgage-programs/options/${queryString}`,
      developerMortgageProgramOptionsSchema,
      { signal },
    ),
    staleTime: 5 * 60_000,
  })
}

export function createDeveloperMortgageProgram(
  payload: DeveloperMortgageProgramWriteRequest,
) {
  return requestJson(
    '/api/v1/developer-mortgage-programs/',
    developerMortgageProgramSchema,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function updateDeveloperMortgageProgram(
  developerProgramIdentifier: number,
  payload: DeveloperMortgageProgramWriteRequest,
) {
  return requestJson(
    `/api/v1/developer-mortgage-programs/${developerProgramIdentifier}/`,
    developerMortgageProgramSchema,
    { method: 'PATCH', body: JSON.stringify(payload) },
  )
}

export function deleteDeveloperMortgageProgram(
  developerProgramIdentifier: number,
) {
  return requestWithoutResponse(
    `/api/v1/developer-mortgage-programs/${developerProgramIdentifier}/`,
    { method: 'DELETE' },
  )
}

export function importDeveloperMortgagePrograms(workbookFile: File) {
  const formData = new FormData()
  formData.append('workbook_file', workbookFile)
  return requestJson(
    '/api/v1/developer-mortgage-programs/import/',
    developerMortgageProgramImportResultSchema,
    { method: 'POST', body: formData },
  )
}

export function keyRateListQueryOptions(searchParameters: URLSearchParams) {
  const normalizedParameters = new URLSearchParams()
  for (const fieldName of ['page', 'pageSize']) {
    const value = searchParameters.get(fieldName)
    if (value) normalizedParameters.set(fieldName, value)
  }
  const queryString = normalizedParameters.toString()
  return queryOptions({
    queryKey: ['key-rates', queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/key-rates/${queryString ? `?${queryString}` : ''}`,
      keyRateListResponseSchema,
      { signal },
    ),
    placeholderData: (previousData) => previousData,
    staleTime: 60_000,
  })
}

export function synchronizeKeyRates() {
  return requestJson(
    '/api/v1/key-rates/sync/',
    keyRateSyncResultSchema,
    { method: 'POST' },
  )
}

export function companyGroupListQueryOptions(
  searchParameters: URLSearchParams,
) {
  const normalizedParameters = new URLSearchParams()
  for (const fieldName of ['q', 'ordering', 'page', 'pageSize']) {
    const value = searchParameters.get(fieldName)
    if (value) normalizedParameters.set(fieldName, value)
  }
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['company-groups', queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/company-groups/${queryString ? `?${queryString}` : ''}`,
      companyGroupListResponseSchema,
      { signal },
    ),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  })
}

export function companyGroupDetailQueryOptions(
  companyGroupIdentifier: number,
) {
  return queryOptions({
    queryKey: ['company-group', companyGroupIdentifier],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/company-groups/${companyGroupIdentifier}/`,
      companyGroupSchema,
      { signal },
    ),
    staleTime: 60_000,
  })
}

export function createCompanyGroup(name: string) {
  return requestJson(
    '/api/v1/company-groups/',
    companyGroupSchema,
    {
      method: 'POST',
      body: JSON.stringify({ name }),
    },
  )
}

export function updateCompanyGroup(
  companyGroupIdentifier: number,
  name: string,
) {
  return requestJson(
    `/api/v1/company-groups/${companyGroupIdentifier}/`,
    companyGroupSchema,
    {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    },
  )
}

export function deleteCompanyGroup(companyGroupIdentifier: number) {
  return requestWithoutResponse(
    `/api/v1/company-groups/${companyGroupIdentifier}/`,
    { method: 'DELETE' },
  )
}

export function propertyDictionaryListQueryOptions(
  dictionaryKey: PropertyDictionaryKey,
  searchParameters: URLSearchParams,
) {
  const normalizedParameters = new URLSearchParams()
  for (const fieldName of ['q', 'status', 'ordering', 'page', 'pageSize']) {
    const value = searchParameters.get(fieldName)
    if (value) normalizedParameters.set(fieldName, value)
  }
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['property-dictionaries', dictionaryKey, queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/property-dictionaries/${dictionaryKey}/${queryString ? `?${queryString}` : ''}`,
      propertyDictionaryListResponseSchema,
      { signal },
    ),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  })
}

export function propertyDictionaryDetailQueryOptions(
  dictionaryKey: PropertyDictionaryKey,
  dictionaryEntryIdentifier: number,
) {
  return queryOptions({
    queryKey: [
      'property-dictionary',
      dictionaryKey,
      dictionaryEntryIdentifier,
    ],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/property-dictionaries/${dictionaryKey}/${dictionaryEntryIdentifier}/`,
      propertyDictionaryEntrySchema,
      { signal },
    ),
    staleTime: 60_000,
  })
}

export function createPropertyDictionaryEntry(
  dictionaryKey: PropertyDictionaryKey,
  payload: PropertyDictionaryWriteRequest,
) {
  return requestJson(
    `/api/v1/property-dictionaries/${dictionaryKey}/`,
    propertyDictionaryEntrySchema,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function updatePropertyDictionaryEntry(
  dictionaryKey: PropertyDictionaryKey,
  dictionaryEntryIdentifier: number,
  payload: PropertyDictionaryWriteRequest,
) {
  return requestJson(
    `/api/v1/property-dictionaries/${dictionaryKey}/${dictionaryEntryIdentifier}/`,
    propertyDictionaryEntrySchema,
    { method: 'PATCH', body: JSON.stringify(payload) },
  )
}

export function deletePropertyDictionaryEntry(
  dictionaryKey: PropertyDictionaryKey,
  dictionaryEntryIdentifier: number,
) {
  return requestWithoutResponse(
    `/api/v1/property-dictionaries/${dictionaryKey}/${dictionaryEntryIdentifier}/`,
    { method: 'DELETE' },
  )
}

export function locationDictionaryListQueryOptions(
  dictionaryKey: LocationDictionaryKey,
  searchParameters: URLSearchParams,
) {
  const normalizedParameters = new URLSearchParams()
  for (const fieldName of [
    'q',
    'status',
    'ordering',
    'regionId',
    'cityId',
    'metroLineId',
    'page',
    'pageSize',
  ]) {
    const value = searchParameters.get(fieldName)
    if (value) normalizedParameters.set(fieldName, value)
  }
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['location-dictionaries', dictionaryKey, queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/location-dictionaries/${dictionaryKey}/${queryString ? `?${queryString}` : ''}`,
      locationDictionaryListResponseSchema,
      { signal },
    ),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  })
}

export function locationDictionaryDetailQueryOptions(
  dictionaryKey: LocationDictionaryKey,
  dictionaryEntryIdentifier: number,
) {
  return queryOptions({
    queryKey: [
      'location-dictionary',
      dictionaryKey,
      dictionaryEntryIdentifier,
    ],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/location-dictionaries/${dictionaryKey}/${dictionaryEntryIdentifier}/`,
      locationDictionaryEntrySchema,
      { signal },
    ),
    staleTime: 60_000,
  })
}

export function locationDictionaryOptionsQueryOptions(
  regionIdentifier: string,
  cityIdentifier: string,
) {
  const searchParameters = new URLSearchParams()
  if (regionIdentifier) searchParameters.set('regionId', regionIdentifier)
  if (cityIdentifier) searchParameters.set('cityId', cityIdentifier)
  const queryString = searchParameters.toString()

  return queryOptions({
    queryKey: ['location-dictionary-options', queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/location-dictionaries/options/${queryString ? `?${queryString}` : ''}`,
      locationDictionaryOptionsSchema,
      { signal },
    ),
    staleTime: 60_000,
  })
}

export function createLocationDictionaryEntry(
  dictionaryKey: LocationDictionaryKey,
  payload: LocationDictionaryWriteRequest,
) {
  return requestJson(
    `/api/v1/location-dictionaries/${dictionaryKey}/`,
    locationDictionaryEntrySchema,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function updateLocationDictionaryEntry(
  dictionaryKey: LocationDictionaryKey,
  dictionaryEntryIdentifier: number,
  payload: LocationDictionaryWriteRequest,
) {
  return requestJson(
    `/api/v1/location-dictionaries/${dictionaryKey}/${dictionaryEntryIdentifier}/`,
    locationDictionaryEntrySchema,
    { method: 'PATCH', body: JSON.stringify(payload) },
  )
}

export function deleteLocationDictionaryEntry(
  dictionaryKey: LocationDictionaryKey,
  dictionaryEntryIdentifier: number,
) {
  return requestWithoutResponse(
    `/api/v1/location-dictionaries/${dictionaryKey}/${dictionaryEntryIdentifier}/`,
    { method: 'DELETE' },
  )
}

export function developerListQueryOptions(
  searchParameters: URLSearchParams,
) {
  const normalizedParameters = new URLSearchParams()
  for (const fieldName of [
    'q',
    'companyGroupId',
    'regionId',
    'status',
    'ordering',
    'page',
    'pageSize',
  ]) {
    const value = searchParameters.get(fieldName)
    if (value) normalizedParameters.set(fieldName, value)
  }
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['developers', queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/developers/${queryString ? `?${queryString}` : ''}`,
      developerListResponseSchema,
      { signal },
    ),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  })
}

export const developerOptionsQueryOptions = queryOptions({
  queryKey: ['developer-options'],
  queryFn: ({ signal }) => requestJson(
    '/api/v1/developers/options/',
    developerOptionsSchema,
    { signal },
  ),
  staleTime: 5 * 60_000,
})

export function developerDetailQueryOptions(developerIdentifier: number) {
  return queryOptions({
    queryKey: ['developer', developerIdentifier],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/developers/${developerIdentifier}/`,
      developerSchema,
      { signal },
    ),
    staleTime: 60_000,
  })
}

export function createDeveloper(payload: DeveloperWriteRequest) {
  return requestJson('/api/v1/developers/', developerSchema, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateDeveloper(
  developerIdentifier: number,
  payload: DeveloperWriteRequest,
) {
  return requestJson(
    `/api/v1/developers/${developerIdentifier}/`,
    developerSchema,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
  )
}

export function deleteDeveloper(developerIdentifier: number) {
  return requestWithoutResponse(
    `/api/v1/developers/${developerIdentifier}/`,
    { method: 'DELETE' },
  )
}

export function importDeveloperRegistry(sourceFile: File) {
  const formData = new FormData()
  formData.append('source_file', sourceFile)
  return requestJson(
    '/api/v1/developers/import-registry/',
    developerRegistryImportSummarySchema,
    { method: 'POST', body: formData },
  )
}

export function realEstateComplexListQueryOptions(
  searchParameters: URLSearchParams,
) {
  const normalizedParameters = new URLSearchParams()
  for (const fieldName of [
    'search',
    'developerId',
    'cityId',
    'realEstateClassId',
    'realEstateTypeId',
    'buildingCount',
    'status',
    'ordering',
    'page',
    'pageSize',
  ]) {
    const value = searchParameters.get(fieldName)
    if (value) normalizedParameters.set(fieldName, value)
  }
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['real-estate-complexes', queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/complexes/${queryString ? `?${queryString}` : ''}`,
      realEstateComplexListResponseSchema,
      { signal },
    ),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  })
}

export function realEstateComplexDetailQueryOptions(
  realEstateComplexIdentifier: number,
) {
  return queryOptions({
    queryKey: ['real-estate-complex', realEstateComplexIdentifier],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/complexes/${realEstateComplexIdentifier}/`,
      realEstateComplexDetailSchema,
      { signal },
    ),
    staleTime: 60_000,
  })
}

export type RealEstateComplexOptionFilters = {
  regionId: number | null
  cityId: number | null
}

export function realEstateComplexOptionsQueryOptions(
  filters: RealEstateComplexOptionFilters,
) {
  const searchParameters = new URLSearchParams()
  if (filters.regionId) {
    searchParameters.set('regionId', String(filters.regionId))
  }
  if (filters.cityId) {
    searchParameters.set('cityId', String(filters.cityId))
  }
  const queryString = searchParameters.toString()
  return queryOptions({
    queryKey: ['real-estate-complex-options', queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/complexes/options/${queryString ? `?${queryString}` : ''}`,
      realEstateComplexOptionsSchema,
      { signal },
    ),
    staleTime: 5 * 60_000,
  })
}

export function createRealEstateComplex(formData: FormData) {
  return requestJson(
    '/api/v1/complexes/',
    realEstateComplexDetailSchema,
    { method: 'POST', body: formData },
  )
}

export function updateRealEstateComplex(
  realEstateComplexIdentifier: number,
  formData: FormData,
) {
  return requestJson(
    `/api/v1/complexes/${realEstateComplexIdentifier}/`,
    realEstateComplexDetailSchema,
    { method: 'PATCH', body: formData },
  )
}

export function deleteRealEstateComplex(
  realEstateComplexIdentifier: number,
) {
  return requestWithoutResponse(
    `/api/v1/complexes/${realEstateComplexIdentifier}/`,
    { method: 'DELETE' },
  )
}

export const mortgageOptionsQueryOptions = queryOptions({
  queryKey: ['mortgage-options'],
  queryFn: ({ signal }) =>
    requestJson('/api/v1/mortgage/options/', mortgageOptionsSchema, { signal }),
  staleTime: 5 * 60_000,
})

export function calculateMortgage(payload: MortgageCalculationRequest) {
  return requestJson(
    '/api/v1/mortgage/calculate/',
    mortgageCalculationResponseSchema,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export function calculateTrenchMortgage(
  payload: TrenchMortgageCalculationRequest,
) {
  return requestJson(
    '/api/v1/mortgage/trench/calculate/',
    trenchMortgageCalculationResponseSchema,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export function saveTrenchMortgageCalculation(
  payload: SavedTrenchMortgageCalculationCreateRequest,
) {
  return requestJson(
    '/api/v1/mortgage/trench/calculations/',
    savedTrenchMortgageCalculationCreateResponseSchema,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export function savedTrenchMortgageCalculationListQueryOptions(
  searchParameters: URLSearchParams,
) {
  const normalizedParameters = new URLSearchParams(searchParameters)
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['saved-trench-mortgage-calculations', queryString],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/v1/mortgage/trench/calculations/${
          queryString ? `?${queryString}` : ''
        }`,
        savedTrenchMortgageCalculationListResponseSchema,
        { signal },
      ),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  })
}

export function savedTrenchMortgageCalculationDetailQueryOptions(
  calculationIdentifier: number,
) {
  return queryOptions({
    queryKey: ['saved-trench-mortgage-calculation', calculationIdentifier],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/v1/mortgage/trench/calculations/${calculationIdentifier}/`,
        savedTrenchMortgageCalculationDetailSchema,
        { signal },
      ),
  })
}

export function deleteSavedTrenchMortgageCalculation(
  calculationIdentifier: number,
) {
  return requestWithoutResponse(
    `/api/v1/mortgage/trench/calculations/${calculationIdentifier}/`,
    { method: 'DELETE' },
  )
}

export function saveMortgageCalculation(
  payload: SavedMortgageCalculationCreateRequest,
) {
  return requestJson(
    '/api/v1/mortgage/calculations/',
    savedMortgageCalculationDetailSchema,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export function savedMortgageCalculationListQueryOptions(
  searchParameters: URLSearchParams,
) {
  const normalizedParameters = new URLSearchParams(searchParameters)
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['saved-mortgage-calculations', queryString],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/v1/mortgage/calculations/${queryString ? `?${queryString}` : ''}`,
        savedMortgageCalculationListResponseSchema,
        { signal },
      ),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  })
}

export function savedMortgageCalculationDetailQueryOptions(
  calculationIdentifier: number,
) {
  return queryOptions({
    queryKey: ['saved-mortgage-calculation', calculationIdentifier],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/v1/mortgage/calculations/${calculationIdentifier}/`,
        savedMortgageCalculationDetailSchema,
        { signal },
      ),
  })
}

export function deleteSavedMortgageCalculation(
  calculationIdentifier: number,
) {
  return requestWithoutResponse(
    `/api/v1/mortgage/calculations/${calculationIdentifier}/`,
    { method: 'DELETE' },
  )
}

export function customerListQueryOptions(searchParameters: URLSearchParams) {
  const normalizedParameters = new URLSearchParams(searchParameters)
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['customers', queryString],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/v1/customers/${queryString ? `?${queryString}` : ''}`,
        customerListResponseSchema,
        { signal },
      ),
    placeholderData: (previousData) => previousData,
  })
}

export function customerDetailQueryOptions(customerIdentifier: number) {
  return queryOptions({
    queryKey: ['customer', customerIdentifier],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/v1/customers/${customerIdentifier}/`,
        customerDetailSchema,
        { signal },
      ),
    staleTime: 60_000,
  })
}

export function customerCalculationListQueryOptions(
  customerIdentifier: number,
  searchParameters: URLSearchParams,
) {
  const normalizedParameters = new URLSearchParams(searchParameters)
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['customer-calculations', customerIdentifier, queryString],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/v1/customers/${customerIdentifier}/calculations/${
          queryString ? `?${queryString}` : ''
        }`,
        customerCalculationListResponseSchema,
        { signal },
      ),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  })
}

export function linkCustomerCalculations(
  customerIdentifier: number,
  payload: CustomerCalculationLinkCreateRequest,
) {
  return requestJson(
    `/api/v1/customers/${customerIdentifier}/calculations/`,
    customerCalculationLinkResponseSchema,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export function unlinkCustomerCalculation(
  customerIdentifier: number,
  programType: CustomerCalculationProgramType,
  linkIdentifier: number,
) {
  return requestWithoutResponse(
    `/api/v1/customers/${customerIdentifier}/calculations/${programType}/${linkIdentifier}/`,
    { method: 'DELETE' },
  )
}

export function exportCustomerCalculationsWord(
  customerIdentifier: number,
  selections: CustomerCalculationSelection[],
) {
  return requestFile(
    `/api/v1/customers/${customerIdentifier}/calculations/export/word/`,
    {
      method: 'POST',
      body: JSON.stringify({ selections }),
    },
    'customer_mortgage_calculations.docx',
  )
}

export function deleteCustomer(customerIdentifier: number) {
  return requestWithoutResponse(`/api/v1/customers/${customerIdentifier}/`, {
    method: 'DELETE',
  })
}

export function customerFormOptionsQueryOptions(
  desiredCityIdentifier: number | null,
) {
  const queryString = desiredCityIdentifier
    ? `?desiredCity=${desiredCityIdentifier}`
    : ''
  return queryOptions({
    queryKey: [
      'customer-form-options',
      desiredCityIdentifier?.toString() ?? '',
    ],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/v1/customers/options/${queryString}`,
        customerFormOptionsSchema,
        { signal },
      ),
    staleTime: 5 * 60_000,
  })
}

export function createCustomer(payload: CustomerWriteRequest) {
  return requestJson(
    '/api/v1/customers/',
    customerMutationResponseSchema,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export function updateCustomer(
  customerIdentifier: number,
  payload: CustomerWriteRequest,
) {
  return requestJson(
    `/api/v1/customers/${customerIdentifier}/`,
    customerMutationResponseSchema,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
  )
}

export function propertyListQueryOptions(searchParameters: URLSearchParams) {
  const normalizedParameters = new URLSearchParams(searchParameters)
  normalizedParameters.delete('customerId')
  const queryString = normalizedParameters.toString()

  return queryOptions({
    queryKey: ['properties', queryString],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/v1/properties/${queryString ? `?${queryString}` : ''}`,
        propertyListResponseSchema,
        { signal },
      ),
    placeholderData: (previousData) => previousData,
  })
}

export function propertyDetailQueryOptions(propertyIdentifier: number) {
  return queryOptions({
    queryKey: ['property', propertyIdentifier],
    queryFn: ({ signal }) =>
      requestJson(
        `/api/v1/properties/${propertyIdentifier}/`,
        propertyDetailSchema,
        { signal },
      ),
    staleTime: 60_000,
  })
}

export type PropertyFormOptionFilters = {
  regionId: number | null
  cityId: number | null
  districtId: number | null
  developerId: number | null
  realEstateComplexId: number | null
}

export function propertyFormOptionsQueryOptions(
  filters: PropertyFormOptionFilters,
) {
  const searchParameters = new URLSearchParams()
  Object.entries(filters).forEach(([fieldName, value]) => {
    if (value) searchParameters.set(fieldName, String(value))
  })
  const queryString = searchParameters.toString()

  return queryOptions({
    queryKey: ['property-form-options', queryString],
    queryFn: ({ signal }) => requestJson(
      `/api/v1/properties/options/${queryString ? `?${queryString}` : ''}`,
      propertyFormOptionsSchema,
      { signal },
    ),
    staleTime: 5 * 60_000,
  })
}

export function createProperty(formData: FormData) {
  return requestJson(
    '/api/v1/properties/',
    propertyDetailSchema,
    {
      method: 'POST',
      body: formData,
    },
  )
}

export function updateProperty(
  propertyIdentifier: number,
  formData: FormData,
) {
  return requestJson(
    `/api/v1/properties/${propertyIdentifier}/`,
    propertyDetailSchema,
    {
      method: 'PATCH',
      body: formData,
    },
  )
}

export function deleteProperty(propertyIdentifier: number) {
  return requestWithoutResponse(
    `/api/v1/properties/${propertyIdentifier}/`,
    { method: 'DELETE' },
  )
}
