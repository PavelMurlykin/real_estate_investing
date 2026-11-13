import { ErrorState } from '@/shared/ui/AsyncState'
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
      <ErrorState headingLevel={1} title="Не удалось открыть страницу" retryLabel="Обновить страницу"
        description="Обновите страницу или выберите другой раздел в меню. Несохранённые изменения при обновлении будут потеряны."
        onRetry={() => window.location.reload()} action={<Link className="button button--secondary" to="/">На главную</Link>} />
    )
  }
}
