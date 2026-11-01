import { useInfiniteQuery } from '@tanstack/react-query'
import { useId, useState } from 'react'

import { requestJson } from '@/api/client'
import { catalogOptionsResponseSchema } from '@/api/schemas'
import type { CatalogOption } from '@/api/schemas'
import { useDebouncedValue } from '@/shared/lib/useDebouncedValue'

type RemoteSelectProps = {
  dictionary: string
  label: string
  value: string
  onChange: (value: string, option?: CatalogOption) => void
  filters?: Record<string, number | string | null | undefined>
  initialOptions?: CatalogOption[]
  truncated?: boolean
  disabled?: boolean
  required?: boolean
  error?: string
}

export function RemoteSelect({
  dictionary, label, value, onChange, filters = {}, initialOptions,
  truncated = false, disabled = false, required = false, error,
}: RemoteSelectProps) {
  const identifier = useId()
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
  const selectedMissing = Boolean(value) && !initialOptions?.some((item) => String(item.id) === value)
  const choicesQuery = useInfiniteQuery({
    queryKey: ['catalog-options', dictionary, filterString, query, value],
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) => {
      const parameters = new URLSearchParams(filterString)
      parameters.set('page', String(pageParam))
      if (query) parameters.set('q', query)
      if (value) parameters.set('selected', value)
      return requestJson(`/api/v1/catalog-options/${dictionary}/?${parameters}`, catalogOptionsResponseSchema, { signal })
    },
    getNextPageParam: (lastPage) => lastPage.nextPage ?? undefined,
    enabled: !disabled && (!initialOptions || remoteActivated || selectedMissing),
    staleTime: 60_000,
  })
  const options = choicesQuery.data
    ? [...new Map(choicesQuery.data.pages.flatMap((page) => [...page.selected, ...page.results])
      .map((option) => [option.id, option])).values()]
    : initialOptions ?? []
  const hasMore = choicesQuery.data ? choicesQuery.hasNextPage : truncated
  return (
    <div className="form-field remote-select">
      <label htmlFor={identifier}>{label}{required ? ' *' : ''}</label>
      <input
        type="search"
        aria-label={`Поиск: ${label}`}
        placeholder="Поиск в справочнике"
        value={search}
        disabled={disabled}
        onChange={(event) => { setSearch(event.target.value); setRemoteActivated(true) }}
        onKeyDown={(event) => { if (event.key === 'Enter') event.preventDefault() }}
      />
      <select
        id={identifier} value={value} disabled={disabled} required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${identifier}-error` : undefined}
        onChange={(event) => onChange(event.target.value,
          options.find((option) => String(option.id) === event.target.value))}
      >
        <option value="">Не выбрано</option>
        {value && !options.some((option) => String(option.id) === value) ? (
          <option value={value}>Загрузка выбранного значения…</option>
        ) : null}
        {options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
      </select>
      {error ? <span className="field-error" id={`${identifier}-error`}>{error}</span> : null}
      {choicesQuery.isFetching ? <small role="status">Загрузка вариантов…</small> : null}
      {choicesQuery.isError ? (
        <button type="button" className="text-button" onClick={() => void choicesQuery.refetch()}>Повторить загрузку справочника</button>
      ) : null}
      {hasMore ? (
        <button type="button" className="text-button" disabled={choicesQuery.isFetching}
          onClick={() => {
            if (!choicesQuery.data) setRemoteActivated(true)
            else void choicesQuery.fetchNextPage()
          }}>
          Показать ещё варианты
        </button>
      ) : null}
    </div>
  )
}
