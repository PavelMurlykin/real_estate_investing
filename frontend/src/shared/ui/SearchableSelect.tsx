import { useId, useRef, useState } from 'react'

export type SelectChoice = { value: string; label: string }

type SearchableSelectProps = {
  label: string
  value: string
  options: SelectChoice[]
  onChange: (value: string) => void
  emptyLabel?: string
  disabled?: boolean
  loading?: boolean
  onSearch?: (query: string) => void
  hasMore?: boolean
  onLoadMore?: () => void
  error?: boolean
  onRetry?: () => void
}

/** One editable control for both searching and selecting a filter value. */
export function SearchableSelect({ label, value, options, onChange, emptyLabel = 'Все', disabled,
  loading, onSearch, hasMore, onLoadMore, error, onRetry }: SearchableSelectProps) {
  const identifier = useId()
  const input = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState<number | null>(null)
  const [chosen, setChosen] = useState<SelectChoice | null>(null)
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
    <div className="form-field searchable-select">
      <label htmlFor={identifier}>{label}</label>
      <div className="searchable-select__control">
        <input id={identifier} ref={input} role="combobox" type="text" autoComplete="off" maxLength={100}
          aria-autocomplete="list" aria-expanded={open} aria-controls={`${identifier}-list`}
          aria-activedescendant={open ? `${identifier}-option-${activeIndex}` : undefined}
          aria-busy={loading || undefined} disabled={disabled}
          value={open ? query : value ? selected?.label ?? 'Загрузка выбранного значения…' : ''}
          placeholder={open ? 'Введите значение' : emptyLabel}
          onFocus={() => setOpen(true)} onBlur={close}
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
      {open ? <ul id={`${identifier}-list`} className="searchable-select__list" role="listbox" aria-label={`Варианты: ${label}`}
        onMouseDown={(event) => event.preventDefault()}
        onScroll={(event) => {
          const element = event.currentTarget
          if (hasMore && !loading && element.scrollHeight - element.scrollTop - element.clientHeight < 48) onLoadMore?.()
        }}>
        {choices.map((option, index) => <li id={`${identifier}-option-${index}`} key={option.value} role="option"
          aria-selected={option.value === value} className={index === activeIndex ? 'is-highlighted' : undefined}
          onMouseMove={() => setActive(index)} onClick={() => choose(option)}>{option.label}</li>)}
        {loading ? <li role="presentation" className="searchable-select__notice">Загрузка…</li> : null}
        {!loading && choices.length === 1 ? <li role="presentation" className="searchable-select__notice">Нет подходящих вариантов</li> : null}
        {error ? <li role="presentation"><button type="button" className="text-button" onClick={onRetry}>Повторить загрузку справочника</button></li> : null}
      </ul> : null}
    </div>
  )
}
