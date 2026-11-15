import { useCallback, useEffect, useId, useLayoutEffect, useRef, type InputHTMLAttributes, type ReactNode } from 'react'

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
    if (disabled || readOnly) return false
    const next = Math.min(maximum, Math.max(minimum, current + direction * increment))
    const nextValue = String(Number(next.toFixed(8)))
    if (nextValue === value) return false
    onValueChange(nextValue)
    return true
  }
  const changeRef = useRef(change)
  const repeatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useLayoutEffect(() => { changeRef.current = change })

  const stopRepeating = useCallback(() => {
    if (repeatTimerRef.current !== null) clearTimeout(repeatTimerRef.current)
    repeatTimerRef.current = null
  }, [])

  useEffect(() => {
    const stopWhenHidden = () => { if (document.hidden) stopRepeating() }
    window.addEventListener('pointerup', stopRepeating)
    window.addEventListener('pointercancel', stopRepeating)
    window.addEventListener('blur', stopRepeating)
    document.addEventListener('visibilitychange', stopWhenHidden)
    return () => {
      stopRepeating()
      window.removeEventListener('pointerup', stopRepeating)
      window.removeEventListener('pointercancel', stopRepeating)
      window.removeEventListener('blur', stopRepeating)
      document.removeEventListener('visibilitychange', stopWhenHidden)
    }
  }, [stopRepeating])

  const startRepeating = (direction: number) => {
    stopRepeating()
    if (!changeRef.current(direction)) return
    const repeat = () => {
      if (changeRef.current(direction)) repeatTimerRef.current = setTimeout(repeat, 100)
      else stopRepeating()
    }
    repeatTimerRef.current = setTimeout(repeat, 400)
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
          {[-1, 1].map((direction) => (
            <button key={direction} type="button" aria-label={`${direction < 0 ? 'Уменьшить' : 'Увеличить'}: ${label}`}
              disabled={disabled || readOnly || (direction < 0 ? current <= minimum : current >= maximum)}
              onPointerDown={(event) => {
                if (event.button === 0 && event.isPrimary !== false) startRepeating(direction)
              }}
              onPointerUp={stopRepeating}
              onPointerCancel={stopRepeating}
              onPointerLeave={stopRepeating}
              onLostPointerCapture={stopRepeating}
              onBlur={stopRepeating}
              onContextMenu={(event) => event.preventDefault()}
              onKeyDown={(event) => {
                if (event.key !== ' ' && event.key !== 'Enter') return
                event.preventDefault()
                if (!event.repeat) startRepeating(direction)
              }}
              onKeyUp={(event) => {
                if (event.key === ' ' || event.key === 'Enter') {
                  event.preventDefault()
                  stopRepeating()
                }
              }}
              // Pointer and keyboard presses change on press; assistive clicks have no press event.
              onClick={(event) => { if (event.detail === 0) change(direction) }}>
              <svg aria-hidden="true" viewBox="0 0 24 24"><path d={direction < 0 ? 'M5 12h14' : 'M5 12h14M12 5v14'} /></svg>
            </button>
          ))}
        </div>
      </div>
      {children}
    </div>
  )
}
