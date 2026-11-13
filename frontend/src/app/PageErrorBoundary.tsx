import { Notice } from '@/shared/ui/Notice'
import { Component, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

type PageErrorBoundaryProps = {
  children: ReactNode
}

export class PageErrorBoundary extends Component<
  PageErrorBoundaryProps,
  { hasError: boolean }
> {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <Notice as="section" tone="error" role="alert" className="state-card state-card--error">

        <div>
          <h1>Не удалось открыть страницу</h1>
          <p>
            Обновите страницу или выберите другой раздел в меню.
            Несохранённые изменения при обновлении будут потеряны.
          </p>
          <div className="page-error-actions">
            <button
              className="button button--secondary"
              type="button"
              onClick={() => window.location.reload()}
            >
              Обновить страницу
            </button>
            <Link className="text-link" to="/">На главную</Link>
          </div>
        </div>
      </Notice>
    )
  }
}
