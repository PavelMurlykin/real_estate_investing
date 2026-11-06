import { useContext } from 'react'
import { UNSAFE_NavigationContext, useSearchParams, type NavigateOptions } from 'react-router-dom'

export function useTableSearchParams() {
  const [parameters, setParameters] = useSearchParams()
  const { navigator } = useContext(UNSAFE_NavigationContext)
  const history = navigator as typeof navigator & { readonly location?: { readonly search: string } }

  const updateParameters = (update: (next: URLSearchParams) => void, options?: NavigateOptions) => {
    // Browser and memory histories update before React commits the new location.
    const next = new URLSearchParams(history.location?.search ?? parameters)
    update(next)
    setParameters(next, options)
  }

  return [parameters, updateParameters] as const
}
