import { queryOptions } from '@tanstack/react-query'

import { requestFile, requestJson, requestWithoutResponse } from './client'
import {
  companyGroupListResponseSchema,
  companyGroupSchema,
  customerCalculationLinkResponseSchema,
  customerCalculationListResponseSchema,
  customerDetailSchema,
  customerFormOptionsSchema,
  customerListResponseSchema,
  customerMutationResponseSchema,
  mortgageCalculationResponseSchema,
  mortgageOptionsSchema,
  overviewSchema,
  propertyDetailSchema,
  propertyFormOptionsSchema,
  propertyListResponseSchema,
  savedMortgageCalculationDetailSchema,
  savedMortgageCalculationListResponseSchema,
  savedTrenchMortgageCalculationCreateResponseSchema,
  savedTrenchMortgageCalculationDetailSchema,
  savedTrenchMortgageCalculationListResponseSchema,
  sessionSchema,
  trenchMortgageCalculationResponseSchema,
} from './schemas'
import type {
  CustomerCalculationLinkCreateRequest,
  CustomerCalculationSelection,
  CustomerCalculationProgramType,
  CustomerWriteRequest,
  MortgageCalculationRequest,
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

export const overviewQueryOptions = queryOptions({
  queryKey: ['overview'],
  queryFn: ({ signal }) =>
    requestJson('/api/v1/overview/', overviewSchema, { signal }),
  staleTime: 60_000,
})

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
