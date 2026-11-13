import { Link } from 'react-router-dom'
import { EmptyState } from '@/shared/ui/AsyncState'

import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'

export function NotFoundPage() {
  useDocumentTitle('Страница не найдена')

  return (
    <EmptyState headingLevel={1} title="Такой страницы нет" description="Возможно, адрес изменился или в ссылке есть ошибка."
      action={<Link className="button button--primary" to="/">
        Вернуться на главную
      </Link>} />
  )
}
