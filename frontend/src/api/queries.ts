import { queryOptions } from '@tanstack/react-query'

import { requestJson, requestWithoutResponse } from './client'
import {
  mortgageCalculationResponseSchema,
  mortgageOptionsSchema,
  overviewSchema,
  propertyDetailSchema,
  propertyListResponseSchema,
  savedMortgageCalculationDetailSchema,
  savedMortgageCalculationListResponseSchema,
  sessionSchema,
} from './schemas'
import type {
  MortgageCalculationRequest,
  SavedMortgageCalculationCreateRequest,
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

export function propertyListQueryOptions(searchParameters: URLSearchParams) {
  const normalizedParameters = new URLSearchParams(searchParameters)
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
