import { useCatalogOptions } from './useCatalogOptions'
import type { CatalogChoicesProps } from './useCatalogOptions'
import { SearchableMultiSelect } from './SearchableSelect'

type RemoteMultiSelectProps = CatalogChoicesProps & {
  label: string
  values: string[]
  onChange: (values: string[]) => void
  error?: string
}

export function RemoteMultiSelect({ label, values, onChange, error, ...choicesProps }: RemoteMultiSelectProps) {
  const { options, searchOptions, choicesQuery, setSearch, remoteSearch, hasMore, loadMore, isSearching } = useCatalogOptions({
    ...choicesProps, values, autoLoad: choicesProps.truncated,
  })
  return <SearchableMultiSelect label={label} values={values} onChange={onChange}
    emptyLabel="Очистить выбор" placeholder="Найти и добавить…" validationError={error}
    options={searchOptions.map((option) => ({ value: String(option.id), label: option.label }))}
    selectedOptions={options.map((option) => ({ value: String(option.id), label: option.label }))}
    disabled={choicesProps.disabled} loading={isSearching} onSearch={remoteSearch ? setSearch : undefined}
    hasMore={hasMore} onLoadMore={loadMore}
    error={choicesQuery.isError} onRetry={() => choicesQuery.refetch()} />
}
