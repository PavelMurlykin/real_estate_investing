import { useId } from 'react'

import type { CatalogOption } from '@/api/schemas'
import { useCatalogOptions } from './useCatalogOptions'
import type { CatalogChoicesProps } from './useCatalogOptions'
import { SearchableSelect } from './SearchableSelect'

type RemoteSelectProps = CatalogChoicesProps & {
  label: string
  value: string
  onChange: (value: string, option?: CatalogOption) => void
  required?: boolean
  error?: string | null
  filter?: boolean
  searchable?: boolean
}

export function RemoteSelect({
  dictionary, label, value, onChange, filters = {}, initialOptions,
  truncated = false, disabled = false, required = false, error, filter = false, searchable = false,
}: RemoteSelectProps) {
  const identifier = useId()
  const { options, choicesQuery, search, setSearch, hasMore, loadMore, isSearching } = useCatalogOptions({
    dictionary, filters, initialOptions, truncated, disabled,
    autoLoad: filter || (searchable && truncated), values: value ? [value] : [],
  })
  const matchingIdentifiers = new Set(choicesQuery.data?.pages.flatMap((page) => page.results.map((option) => option.id)))
  const remoteSearch = filter || truncated || !initialOptions || Boolean(choicesQuery.data)
    || Boolean(value && !initialOptions.some((option) => String(option.id) === value))
  if (filter || searchable) return (
    <SearchableSelect label={label + (required ? ' *' : '')} value={value}
      emptyLabel={filter ? 'Все' : 'Не выбрано'} required={required} validationError={error}
      options={options.filter((option) => (!remoteSearch || !search.trim() || matchingIdentifiers.has(option.id))
        && (choicesQuery.data || !choicesQuery.isFetching || String(option.id) === value))
        .map((option) => ({ value: String(option.id), label: option.label }))}
      onChange={(next) => {
        if (searchable && next === value) return
        onChange(next, options.find((option) => String(option.id) === next))
      }}
      disabled={disabled} loading={isSearching} onSearch={remoteSearch ? setSearch : undefined} hasMore={hasMore} onLoadMore={loadMore}
      error={choicesQuery.isError} onRetry={() => void choicesQuery.refetch()} />
  )
  return (
    <div className="form-field remote-select">
      <label htmlFor={identifier}>{label}{required ? ' *' : ''}</label>
      <input
        type="search"
        aria-label={`Поиск: ${label}`}
        placeholder="Поиск в справочнике"
        value={search}
        disabled={disabled}
        onChange={(event) => setSearch(event.target.value)}
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
          onClick={loadMore}>
          {!choicesQuery.data && !options.length ? 'Загрузить варианты' : 'Показать ещё варианты'}
        </button>
      ) : null}
    </div>
  )
}
