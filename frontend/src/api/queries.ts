import { queryOptions } from '@tanstack/react-query'

import { requestJson } from './client'
import {
  mortgageCalculationResponseSchema,
  mortgageOptionsSchema,
  overviewSchema,
  propertyListResponseSchema,
  sessionSchema,
} from './schemas'
import type { MortgageCalculationRequest } from './schemas'

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
