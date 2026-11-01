import { useDebouncedValue } from './useDebouncedValue'

export function useTableParameters(parameters: URLSearchParams) {
  const queryString = useDebouncedValue(parameters.toString())
  return new URLSearchParams(queryString)
}
