import { createContext, useContext, useEffect, type RefObject } from 'react'

export type LoadingFocusTarget = { element: HTMLElement; pathname: string; main: HTMLElement | null; label: string }
export const LoadingFocusContext = createContext<RefObject<LoadingFocusTarget | null> | null>(null)

export function controlLabel(element: HTMLElement) {
  const labels = 'labels' in element ? (element as HTMLInputElement).labels : null
  return element.getAttribute('aria-label') ?? [...labels ?? []].map((label) => label.textContent?.trim()).join(' ')
}

export function useLoadingFocus(compact: boolean) {
  const memory = useContext(LoadingFocusContext)
  useEffect(() => {
    const snapshot = memory?.current
    if (compact || !snapshot || snapshot.pathname !== window.location.pathname
      || document.activeElement !== document.body || (snapshot.element.isConnected && snapshot.element.getClientRects().length)) return
    const ownsFocus = () => memory?.current === snapshot
    return () => {
      window.requestAnimationFrame(() => {
        if (!ownsFocus() || snapshot.pathname !== window.location.pathname
          || document.activeElement !== document.body || !snapshot.main?.isConnected) return
        const byId = snapshot.element.id ? document.getElementById(snapshot.element.id) : null
        const labelled = snapshot.label ? [...snapshot.main.querySelectorAll<HTMLElement>('input, select, textarea, button, a[href]')]
          .find((element) => controlLabel(element) === snapshot.label && !element.matches(':disabled')) : null
        const target = byId ?? labelled ?? snapshot.main.querySelector<HTMLElement>('h1, h2, h3')
        if (target) {
          if (!target.matches('input, select, textarea, button, a[href]')) target.setAttribute('tabindex', '-1')
          // Restoring the selection control must not reopen its completed search.
          target.setAttribute('data-restoring-focus', '')
          try { target.focus() } finally { target.removeAttribute('data-restoring-focus') }
        }
      })
    }
  }, [compact, memory])
}
