import type { ReactNode } from 'react'

type ErrorStateProps = {
  onRetry: () => void
  title?: string
}

export function ErrorState({
  onRetry,
  title = 'Не удалось загрузить данные',
}: ErrorStateProps) {
  return (
    <section className="state-card state-card--error" role="alert">
      <div className="state-card__icon" aria-hidden="true">
        !
      </div>
      <div>
        <h2>{title}</h2>
        <p>Проверьте подключение и повторите запрос.</p>
        <button className="button button--secondary" type="button" onClick={onRetry}>
          Повторить
        </button>
      </div>
    </section>
  )
}

type EmptyStateProps = {
  title: string
  description: string
  action?: ReactNode
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <section className="state-card">
      <div className="state-card__icon" aria-hidden="true">
        ◇
      </div>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
        {action}
      </div>
    </section>
  )
}

export function PageLoadingState() {
  return (
    <div className="page-loading" role="status" aria-label="Загрузка данных">
      <div className="skeleton skeleton--wide" />
      <div className="skeleton-grid">
        <div className="skeleton skeleton--card" />
        <div className="skeleton skeleton--card" />
        <div className="skeleton skeleton--card" />
      </div>
      <span className="visually-hidden">Загрузка…</span>
    </div>
  )
}
