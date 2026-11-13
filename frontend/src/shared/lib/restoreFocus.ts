function isVisible(element: HTMLElement) {
  for (let current: HTMLElement | null = element; current; current = current.parentElement) {
    const style = getComputedStyle(current)
    if (current.hidden || current.inert || style.display === 'none' || style.visibility === 'hidden') return false
  }
  return true
}

export function restoreFocus(trigger: Element | null) {
  if (trigger instanceof HTMLElement && trigger.isConnected && isVisible(trigger)
    && !trigger.matches(':disabled')) {
    trigger.focus()
    return
  }
  const fallback = document.querySelector<HTMLElement>('main h1') ?? document.querySelector<HTMLElement>('main')
  if (fallback) { fallback.tabIndex = -1; fallback.focus() }
}

export function dialogControls(dialog: HTMLDialogElement) {
  return [...dialog.querySelectorAll<HTMLElement>(
    'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
  )].filter((element) => element.tabIndex >= 0 && isVisible(element))
}
