import { useInfiniteQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { requestJson } from '@/api/client'
import { catalogOptionsResponseSchema } from '@/api/schemas'
import type { CatalogOption } from '@/api/schemas'
import { useDebouncedValue } from '@/shared/lib/useDebouncedValue'

export type CatalogChoicesProps = {
  dictionary: string
  filters?: Record<string, number | string | null | undefined>
  initialOptions?: CatalogOption[]
  truncated?: boolean
  disabled?: boolean
  autoLoad?: boolean
}

export function useCatalogOptions({
  dictionary, filters = {}, initialOptions, truncated = false, disabled = false,
  values, autoLoad = false,
}: CatalogChoicesProps & { values: string[] }) {
  const [search, setSearch] = useState('')
  const [remoteActivated, setRemoteActivated] = useState(false)
  const query = useDebouncedValue(search.trim())
  const filterParameters = new URLSearchParams()
  Object.entries(filters).sort().forEach(([name, filterValue]) => {
    if (filterValue !== null && filterValue !== undefined && filterValue !== '') {
      filterParameters.set(name, String(filterValue))
    }
  })
  const filterString = filterParameters.toString()
  const selectedMissing = values.some((value) => !initialOptions?.some((item) => String(item.id) === value))
  const choicesQuery = useInfiniteQuery({
    queryKey: ['catalog-options', dictionary, filterString, query, values.join(',')],
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) => {
      const parameters = new URLSearchParams(filterString)
      parameters.set('page', String(pageParam))
      if (query) parameters.set('q', query)
      values.forEach((value) => parameters.append('selectedIds', value))
      return requestJson(`/api/v1/catalog-options/${dictionary}/?${parameters}`, catalogOptionsResponseSchema, { signal })
    },
    getNextPageParam: (lastPage) => lastPage.nextPage ?? undefined,
    placeholderData: (previous, previousQuery) => (
      previousQuery?.queryKey[1] === dictionary && previousQuery.queryKey[2] === filterString ? previous : undefined
    ),
    enabled: !disabled && (autoLoad || !initialOptions || remoteActivated || selectedMissing),
    staleTime: 60_000,
  })
  const options = choicesQuery.data
    ? [...new Map(choicesQuery.data.pages.flatMap((page) => [...page.selected, ...page.results])
      .map((option) => [option.id, option])).values()]
    : initialOptions ?? []
  return {
    options, choicesQuery, search, isSearching: choicesQuery.isFetching || query !== search.trim(),
    setSearch: (value: string) => { setSearch(value); setRemoteActivated(true) },
    hasMore: choicesQuery.data ? choicesQuery.hasNextPage : truncated,
    loadMore: () => {
      if (!choicesQuery.data) setRemoteActivated(true)
      else void choicesQuery.fetchNextPage()
    },
  }
}
