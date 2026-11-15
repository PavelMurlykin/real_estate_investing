import { useId, type InputHTMLAttributes, type ReactNode } from 'react'

type NumberFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'value' | 'onChange' | 'children'> & {
  label: string
  value: string
  onValueChange: (value: string) => void
  increment?: number
  children?: ReactNode
}

export function NumberField({ label, value, onValueChange, increment = 1, children,
  className = '', id, min, max, disabled, readOnly, onKeyDown, ...inputProps }: NumberFieldProps) {
  const identifier = useId()
  const inputIdentifier = id ?? identifier
  const minimum = min === undefined ? -Infinity : Number(min)
  const maximum = max === undefined ? Infinity : Number(max)
  const current = value.trim() === '' || !Number.isFinite(Number(value)) ? 0 : Number(value)
  const change = (direction: number) => {
    if (disabled || readOnly) return
    const next = Math.min(maximum, Math.max(minimum, current + direction * increment))
    onValueChange(String(Number(next.toFixed(8))))
  }

  return (
    <div className={`form-field ${className}`}>
      <label htmlFor={inputIdentifier}>{label}</label>
      <div className="number-field">
        <input {...inputProps} id={inputIdentifier} type="number" value={value}
          min={min} max={max} disabled={disabled} readOnly={readOnly}
          onChange={(event) => onValueChange(event.target.value)}
          onKeyDown={(event) => {
            onKeyDown?.(event)
            if (!event.defaultPrevented && ['ArrowUp', 'ArrowDown'].includes(event.key)) {
              event.preventDefault()
              change(event.key === 'ArrowUp' ? 1 : -1)
            }
          }} />
        <div className="number-field__buttons">
          <button type="button" aria-label={`Уменьшить: ${label}`}
            disabled={disabled || readOnly || current <= minimum} onClick={() => change(-1)}>
            <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 12h14" /></svg>
          </button>
          <button type="button" aria-label={`Увеличить: ${label}`}
            disabled={disabled || readOnly || current >= maximum} onClick={() => change(1)}>
            <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 12h14M12 5v14" /></svg>
          </button>
        </div>
      </div>
      {children}
    </div>
  )
}
