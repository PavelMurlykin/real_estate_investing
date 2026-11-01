import { useId } from 'react'
import { useSearchParams } from 'react-router-dom'

type LiveFilterInputProps = {
  label: string
  caption?: string
  parameter: string
  pageParameter?: string
  type?: 'search' | 'number'
  placeholder?: string
  max?: number
}

export function LiveFilterInput({ label, caption, parameter, pageParameter = 'page', type = 'search', placeholder, max }: LiveFilterInputProps) {
  const identifier = useId()
  const [parameters, setParameters] = useSearchParams()
  return (
    <label className="form-field" htmlFor={identifier}>
      <span>{caption ?? label}</span>
      <input id={identifier} aria-label={label} name={parameter} type={type} step={type === 'number' ? '0.01' : undefined}
        min={type === 'number' ? 0 : undefined} max={max} placeholder={placeholder}
        value={parameters.get(parameter) ?? ''}
        onChange={(event) => {
          const value = event.target.value
          if (type === 'number' && value && (Number(value) < 0 || (max !== undefined && Number(value) > max))) return
          const next = new URLSearchParams(parameters)
          if (value) next.set(parameter, value)
          else next.delete(parameter)
          next.delete(pageParameter)
          setParameters(next, { replace: true })
        }} />
    </label>
  )
}
