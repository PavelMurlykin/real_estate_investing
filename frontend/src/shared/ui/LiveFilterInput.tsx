import { useId } from 'react'

import { useTableSearchParams } from '@/shared/lib/useTableSearchParams'

type LiveFilterInputProps = {
  label: string
  id?: string
  caption?: string
  parameter: string
  pageParameter?: string
  type?: 'search' | 'number'
  placeholder?: string
  max?: number
}

export function LiveFilterInput({ label, id, caption, parameter, pageParameter = 'page', type = 'search', placeholder, max }: LiveFilterInputProps) {
  const generatedIdentifier = useId()
  const identifier = id ?? generatedIdentifier
  const [parameters, updateParameters] = useTableSearchParams()
  return (
    <label className="form-field" htmlFor={identifier}>
      <span>{caption ?? label}</span>
      <input id={identifier} aria-label={label} name={parameter} type={type} step={type === 'number' ? '0.01' : undefined}
        min={type === 'number' ? 0 : undefined} max={max} placeholder={placeholder}
        value={parameters.get(parameter) ?? ''}
        onChange={(event) => {
          const value = event.target.value
          if (type === 'number' && value && (Number(value) < 0 || (max !== undefined && Number(value) > max))) return
          updateParameters((next) => {
            if (value) next.set(parameter, value)
            else next.delete(parameter)
            next.delete(pageParameter)
          }, { replace: true })
        }} />
    </label>
  )
}
