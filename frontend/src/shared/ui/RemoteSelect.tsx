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
  truncated = false, disabled = false, required = false, error, filter = false,
}: RemoteSelectProps) {
  const { options, searchOptions, choicesQuery, setSearch, remoteSearch, hasMore, loadMore, isSearching } = useCatalogOptions({
    dictionary, filters, initialOptions, truncated, disabled,
    autoLoad: filter || truncated, values: value ? [value] : [],
  })
  return (
    <SearchableSelect label={label + (required ? ' *' : '')} value={value}
      emptyLabel={filter ? 'Все' : 'Не выбрано'} required={required} validationError={error}
      options={searchOptions.map((option) => ({ value: String(option.id), label: option.label }))}
      selectedOptions={options.map((option) => ({ value: String(option.id), label: option.label }))}
      onChange={(next) => {
        if (!filter && next === value) return
        onChange(next, options.find((option) => String(option.id) === next))
      }}
      disabled={disabled} loading={isSearching} onSearch={remoteSearch || filter ? setSearch : undefined} hasMore={hasMore} onLoadMore={loadMore}
      error={choicesQuery.isError} onRetry={() => void choicesQuery.refetch()} />
  )
}
