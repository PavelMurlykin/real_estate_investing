import { useEffect, useId, useRef, useState } from 'react'

export type SelectChoice = { value: string; label: string }

type SearchableSelectProps = {
  label: string
  value: string
  options: SelectChoice[]
  onChange: (value: string) => void
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

/** One editable control for searching and selecting a dictionary value. */
export function SearchableSelect({ label, value, options, onChange, emptyLabel = 'Все', placeholder, disabled,
  required, validationError, loading, onSearch, hasMore, onLoadMore, error, onRetry }: SearchableSelectProps) {
  const identifier = useId()
  const input = useRef<HTMLInputElement>(null)
  const popup = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState<number | null>(null)
  const [chosen, setChosen] = useState<SelectChoice | null>(null)
  useEffect(() => {
    if (open) popup.current?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
  }, [open])
  const selected = options.find((option) => option.value === value) ?? (chosen?.value === value ? chosen : undefined)
  const choices = [{ value: '', label: emptyLabel }, ...options.filter((option) => (
    !query || onSearch || option.label.toLocaleLowerCase('ru-RU').includes(query.toLocaleLowerCase('ru-RU'))
  ))]
  const activeIndex = Math.min(active ?? (query.trim() ? 1 : Math.max(0, choices.findIndex((choice) => choice.value === value))), choices.length - 1)
  const close = () => { setOpen(false); setQuery(''); onSearch?.(''); setActive(null) }
  const choose = (choice: SelectChoice) => { setChosen(choice); onChange(choice.value); close() }
  const move = (index: number) => {
    const next = Math.max(0, Math.min(index, choices.length - 1))
    setActive(next)
    document.getElementById(`${identifier}-option-${next}`)?.scrollIntoView?.({ block: 'nearest' })
  }
  return (
    <div className="form-field searchable-select" onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) close()
    }}>
      <label htmlFor={identifier}>{label}</label>
      <div className="searchable-select__control">
        <input id={identifier} ref={input} role="combobox" type="text" autoComplete="off" maxLength={100}
          aria-autocomplete="list" aria-expanded={open} aria-controls={`${identifier}-list`}
          aria-activedescendant={open ? `${identifier}-option-${activeIndex}` : undefined}
          aria-busy={loading || undefined} disabled={disabled} required={required}
          aria-invalid={Boolean(validationError)}
          aria-describedby={validationError ? `${identifier}-error` : undefined}
          value={open ? query : value ? selected?.label ?? 'Загрузка выбранного значения…' : ''}
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
            onMouseDown={(event) => event.preventDefault()}
            onScroll={(event) => {
              const element = event.currentTarget
              if (hasMore && !loading && element.scrollHeight - element.scrollTop - element.clientHeight < 48) onLoadMore?.()
            }}>
            {choices.map((option, index) => <li id={`${identifier}-option-${index}`} key={option.value} role="option"
              aria-selected={option.value === value} className={index === activeIndex ? 'is-highlighted' : undefined}
              onMouseMove={() => setActive(index)} onClick={() => choose(option)}>{option.label}</li>)}
            {loading ? <li role="presentation" className="searchable-select__notice">Загрузка…</li> : null}
            {!loading && !error && choices.length === 1 ? (
              <li role="presentation" className="searchable-select__notice">Нет подходящих вариантов</li>
            ) : null}
          </ul>
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
