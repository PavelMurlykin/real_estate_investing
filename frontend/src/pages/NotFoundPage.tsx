import { Link } from 'react-router-dom'

import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'

export function NotFoundPage() {
  useDocumentTitle('Страница не найдена')

  return (
    <section className="not-found">
      <span>404</span>
      <h1>Такой страницы нет</h1>
      <p>Возможно, адрес изменился или в ссылке есть ошибка.</p>
      <Link className="button button--primary" to="/">
        Вернуться на главную
      </Link>
    </section>
  )
}
