import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useLoadingFocus } from '@/shared/lib/loadingFocus'

type StatePanelProps = {
  kind: 'loading' | 'error' | 'empty'
  title: string
  description?: string
  action?: ReactNode
  compact?: boolean
  headingLevel?: 1 | 2 | 3
  busy?: boolean
  className?: string
}

function StatePanel({ kind, title, description, action, compact = false, headingLevel, busy, className = '' }: StatePanelProps) {
  const identifier = useId()
  const Heading = headingLevel === 1 ? 'h1' : headingLevel === 3 || compact ? 'h3' : 'h2'
  return <section className={`async-state async-state--${kind}${compact ? ' async-state--compact' : ''} ${className}`}
    role={kind === 'error' ? 'alert' : kind === 'loading' ? 'status' : undefined}
    aria-label={kind === 'loading' ? 'Загрузка данных' : undefined}
    aria-labelledby={kind === 'loading' ? undefined : `${identifier}-title`}
    aria-describedby={description ? `${identifier}-description` : undefined}
    aria-busy={kind === 'loading' || busy || undefined} aria-atomic="true">
    <svg className={`async-state__icon${kind === 'loading' ? ' async-state__spinner' : ''}`} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      {kind === 'empty' ? <><path d="M4 8h16v12H4zM8 4h8v4M4 13h5l1 2h4l1-2h5" /></>
        : kind === 'error' ? <><circle cx="12" cy="12" r="9" /><path d="M12 7v7m0 3v1" /></>
          : <path d="M21 12a9 9 0 1 1-9-9" />}
    </svg>
    <div className="async-state__body">
      <Heading id={`${identifier}-title`}>{title}</Heading>
      {description ? <p id={`${identifier}-description`}>{description}</p> : null}
      {kind === 'loading' && title !== 'Загрузка…' ? <span className="visually-hidden">Загрузка…</span> : null}
      {action ? <div className="async-state__actions">{action}</div> : null}
    </div>
  </section>
}

type ErrorStateProps = {
  onRetry: () => void | Promise<unknown>
  title?: string
  description?: string
  compact?: boolean
  headingLevel?: 1 | 2
  retryLabel?: string
  action?: ReactNode
  isRetrying?: boolean
}

export function RetryButton({ onRetry, label = 'Повторить', isRetrying = false }: {
  onRetry: () => void | Promise<unknown>; label?: string; isRetrying?: boolean
}) {
  const [retrying, setRetrying] = useState(false)
  const inFlight = useRef(false)
  const button = useRef<HTMLButtonElement>(null)
  const focusRecovery = useRef<{ settled: boolean; restore: () => void } | null>(null)
  useEffect(() => {
    const recovery = focusRecovery
    return () => {
      if (recovery.current?.settled) window.requestAnimationFrame(recovery.current.restore)
    }
  }, [])
  const retry = async () => {
    if (inFlight.current || isRetrying) return
    inFlight.current = true
    setRetrying(true)
    const trigger = button.current
    const scope = trigger?.closest('.async-state')?.parentElement
    const main = trigger?.closest('main')
    const address = window.location.href
    let observer: MutationObserver | undefined
    const restore = () => {
      observer?.disconnect()
      if (window.location.href !== address) return
      const active = document.activeElement
      if (active !== document.body && active !== trigger && active?.isConnected) return
      const container = scope?.isConnected ? scope : main?.isConnected ? main : null
      if (container?.querySelector(':scope > .async-state--loading')) {
        observer = new MutationObserver(() => window.requestAnimationFrame(restore))
        observer.observe(container, { childList: true, subtree: true })
        return
      }
      const target = container?.querySelector<HTMLElement>('[data-async-retry]:not(:disabled)')
        ?? container?.querySelector<HTMLElement>('h1, h2, h3')
        ?? container?.querySelector<HTMLElement>('[role="region"]:not([hidden]), a[href], button:not(:disabled)')
      if (target) { if (!target.matches('button, a[href]')) target.setAttribute('tabindex', '-1'); target.focus() }
    }
    focusRecovery.current = { settled: false, restore }
    try { await onRetry() } catch { /* The error panel remains available for another attempt. */ }
    finally {
      inFlight.current = false
      setRetrying(false)
      focusRecovery.current!.settled = true
      window.requestAnimationFrame(restore)
    }
  }
  return <button ref={button} data-async-retry className="button button--secondary" type="button"
    aria-busy={retrying || isRetrying || undefined} disabled={retrying || isRetrying} onClick={() => void retry()}>
    {retrying || isRetrying ? 'Повторяем…' : label}
  </button>
}

export function ErrorState({ onRetry, title = 'Не удалось загрузить данные',
  description = 'Проверьте подключение и повторите запрос.', compact, headingLevel,
  retryLabel = 'Повторить', action, isRetrying = false }: ErrorStateProps) {
  return <StatePanel kind="error" title={title} description={description} compact={compact} headingLevel={headingLevel}
    busy={isRetrying} action={<><RetryButton onRetry={onRetry} label={retryLabel} isRetrying={isRetrying} />{action}</>} />
}

type EmptyStateProps = { title: string; description?: string; action?: ReactNode; compact?: boolean; headingLevel?: 1 | 2 }
export function EmptyState(props: EmptyStateProps) { return <StatePanel kind="empty" {...props} /> }

export function PageLoadingState({ title = 'Загрузка…', compact = false, className }: { title?: string; compact?: boolean; className?: string }) {
  useLoadingFocus(compact)
  return <StatePanel kind="loading" title={title} compact={compact} className={className} />
}
