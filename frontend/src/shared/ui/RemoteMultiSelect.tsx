import { useId } from 'react'

import { useCatalogOptions } from './useCatalogOptions'
import type { CatalogChoicesProps } from './useCatalogOptions'

type RemoteMultiSelectProps = CatalogChoicesProps & {
  label: string
  values: string[]
  onChange: (values: string[]) => void
  error?: string
  mode?: 'checkbox' | 'select'
}

export function RemoteMultiSelect({
  label, values, onChange, error, mode = 'checkbox', ...choicesProps
}: RemoteMultiSelectProps) {
  const identifier = useId()
  const { options, choicesQuery, search, setSearch, hasMore, loadMore } = useCatalogOptions({ ...choicesProps, values })
  return (
    <fieldset className="form-field form-field--wide customer-choice-field remote-select" aria-describedby={error ? `${identifier}-error` : undefined}>
      <legend>{label}</legend>
      <input type="search" aria-label={`Поиск: ${label}`} value={search}
        disabled={choicesProps.disabled} placeholder="Поиск в справочнике"
        onChange={(event) => setSearch(event.target.value)}
        onKeyDown={(event) => { if (event.key === 'Enter') event.preventDefault() }} />
      {mode === 'select' ? (
        <>
          <select multiple aria-label={label} value={values} disabled={choicesProps.disabled}
            aria-invalid={Boolean(error)}
            onChange={(event) => onChange(Array.from(event.target.selectedOptions, (option) => option.value))}>
            {options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
          </select>
          <small>Для выбора нескольких значений используйте Ctrl или Cmd.</small>
        </>
      ) : (
        <div className="customer-choice-grid">
          {options.map((option) => (
            <label key={option.id}>
              <input type="checkbox" value={option.id} checked={values.includes(String(option.id))}
                disabled={choicesProps.disabled}
                onChange={(event) => onChange(event.target.checked
                  ? [...values, String(option.id)] : values.filter((value) => value !== String(option.id)))} />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      )}
      {!options.length && !choicesQuery.isFetching ? <small>Нет доступных вариантов</small> : null}
      {error ? <span className="field-error" id={`${identifier}-error`}>{error}</span> : null}
      {choicesQuery.isFetching ? <small role="status">Загрузка вариантов…</small> : null}
      {choicesQuery.isError ? <button type="button" className="text-button" onClick={() => void choicesQuery.refetch()}>Повторить загрузку справочника</button> : null}
      {hasMore ? <button type="button" className="text-button" disabled={choicesQuery.isFetching} onClick={loadMore}>Показать ещё варианты</button> : null}
    </fieldset>
  )
}
