import { useEffect, useId, useRef, useState } from 'react'

export type SelectChoice = { value: string; label: string }

type SearchableChoicesProps = {
  label: string
  options: SelectChoice[]
  selectedOptions?: SelectChoice[]
  emptyLabel?: string
  placeholder?: string
  disabled?: boolean
  required?: boolean
  validationError?: string | null
  loading?: boolean
  onSearch?: (query: string) => void
  hasMore?: boolean
  onLoadMore?: () => void
  error?: boolean
  onRetry?: () => void
}

type SearchableSelectProps = SearchableChoicesProps & {
  value: string
  onChange: (value: string) => void
}

/** One editable control for searching and selecting a dictionary value. */
export function SearchableSelect({ value, onChange, ...props }: SearchableSelectProps) {
  return <SearchableChoices {...props} values={value ? [value] : []}
    onChange={(values) => onChange(values[0] ?? '')} />
}

export function SearchableMultiSelect(props: SearchableChoicesProps & {
  values: string[]
  onChange: (values: string[]) => void
}) {
  return <SearchableChoices {...props} multiple />
}

function SearchableChoices({ label, values, options, selectedOptions, onChange, multiple = false, emptyLabel = 'Все', placeholder, disabled,
  required, validationError, loading, onSearch, hasMore, onLoadMore, error, onRetry }: SearchableChoicesProps & {
    values: string[]
    onChange: (values: string[]) => void
    multiple?: boolean
  }) {
  const identifier = useId()
  const input = useRef<HTMLInputElement>(null)
  const popup = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState<number | null>(null)
  const [chosen, setChosen] = useState<SelectChoice[]>([])
  useEffect(() => {
    if (open) popup.current?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
  }, [open])
  const value = values[0] ?? ''
  const selected = (identifier: string) => options.find((option) => option.value === identifier)
    ?? selectedOptions?.find((option) => option.value === identifier)
    ?? chosen.find((option) => option.value === identifier)
  const choices = [{ value: '', label: emptyLabel }, ...options.filter((option) => (
    !query || onSearch || option.label.toLocaleLowerCase('ru-RU').includes(query.toLocaleLowerCase('ru-RU'))
  ))]
  const activeIndex = Math.min(active ?? (query.trim() ? 1 : Math.max(0, choices.findIndex((choice) => choice.value === value))), choices.length - 1)
  const close = () => { setOpen(false); setQuery(''); onSearch?.(''); setActive(null) }
  const choose = (choice: SelectChoice) => {
    setChosen((current) => [...current.filter((option) => option.value !== choice.value), choice])
    onChange(multiple && choice.value
      ? values.includes(choice.value) ? values.filter((value) => value !== choice.value) : [...values, choice.value]
      : choice.value ? [choice.value] : [])
    if (multiple) { setQuery(''); onSearch?.(''); setActive(null) }
    else close()
  }
  const move = (index: number) => {
    const next = Math.max(0, Math.min(index, choices.length - 1))
    setActive(next)
    document.getElementById(`${identifier}-option-${next}`)?.scrollIntoView?.({ block: 'nearest' })
  }
  return (
    <div className={`form-field searchable-select${multiple ? ' form-field--wide' : ''}`} onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) close()
    }}>
      <label htmlFor={identifier}>{label}</label>
      {multiple && values.length ? <ul className="searchable-select__values" aria-label={`Выбрано: ${label}`}>
        {values.map((value) => <li key={value}>
          <span>{selected(value)?.label ?? 'Загрузка выбранного значения…'}</span>
          <button type="button" className="text-button" disabled={disabled}
            aria-label={`Убрать: ${selected(value)?.label ?? value}`}
            onClick={() => { input.current?.focus(); onChange(values.filter((item) => item !== value)) }}>
            Убрать
          </button>
        </li>)}
      </ul> : null}
      <div className="searchable-select__control">
        <input id={identifier} ref={input} role="combobox" type="text" autoComplete="off" maxLength={100}
          aria-autocomplete="list" aria-expanded={open} aria-controls={`${identifier}-list`}
          aria-activedescendant={open && choices[activeIndex] ? `${identifier}-option-${activeIndex}` : undefined}
          aria-busy={loading || undefined} disabled={disabled} required={required}
          aria-invalid={Boolean(validationError)}
          aria-describedby={validationError ? `${identifier}-error` : undefined}
          value={open ? query : !multiple && value ? selected(value)?.label ?? 'Загрузка выбранного значения…' : ''}
          placeholder={placeholder ?? (open ? 'Введите значение' : emptyLabel)}
          onFocus={() => setOpen(true)}
          onClick={() => setOpen(true)}
          onChange={(event) => { setQuery(event.target.value); onSearch?.(event.target.value); setActive(null); setOpen(true) }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') { event.preventDefault(); close() }
            else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
              event.preventDefault(); setOpen(true)
              if (open) move(activeIndex + (event.key === 'ArrowDown' ? 1 : -1))
              else setActive(null)
            } else if (event.key === 'Enter' && open) {
              event.preventDefault()
              if (query.trim() && (loading || choices.length === 1)) return
              choose(choices[activeIndex])
            }
          }} />
        <span className="searchable-select__chevron" aria-hidden="true">⌄</span>
      </div>
      {validationError ? <span className="field-error" id={`${identifier}-error`}>{validationError}</span> : null}
      {open ? (
        <div className="searchable-select__popup" ref={popup}>
          <ul id={`${identifier}-list`} className="searchable-select__list" role="listbox" aria-label={`Варианты: ${label}`} tabIndex={-1}
            aria-multiselectable={multiple || undefined}
            onMouseDown={(event) => event.preventDefault()}
            onScroll={(event) => {
              const element = event.currentTarget
              if (hasMore && !loading && element.scrollHeight - element.scrollTop - element.clientHeight < 48) onLoadMore?.()
            }}>
            {choices.map((option, index) => <li id={`${identifier}-option-${index}`} key={option.value} role="option"
              aria-selected={option.value ? values.includes(option.value) : !values.length} className={index === activeIndex ? 'is-highlighted' : undefined}
              onMouseMove={() => setActive(index)} onClick={() => choose(option)}>
              {option.label}
            </li>)}
            {loading ? <li role="presentation" className="searchable-select__notice">Загрузка…</li> : null}
            {!loading && !error && choices.length === 1 ? (
              <li role="presentation" className="searchable-select__notice">Нет подходящих вариантов</li>
            ) : null}
          </ul>
          {hasMore && !error && onLoadMore ? <button type="button" className="text-button searchable-select__retry" disabled={loading}
            onClick={() => { input.current?.focus(); onLoadMore() }}>
            Показать ещё варианты
          </button> : null}
          {error && onRetry ? (
            <button
              type="button"
              className="text-button searchable-select__retry"
              onClick={() => { input.current?.focus(); onRetry() }}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.preventDefault()
                  input.current?.focus()
                  close()
                }
              }}
            >
              Повторить загрузку справочника
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
