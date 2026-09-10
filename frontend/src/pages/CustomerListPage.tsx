import { useQuery } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import {
  customerListQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type { CustomerListItem } from '@/api/schemas'
import { formatDateTime, formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

const orderingOptions = [
  { value: '-createdAt', label: 'Сначала новые' },
  { value: 'createdAt', label: 'Сначала старые' },
  { value: 'name', label: 'По имени: А–Я' },
  { value: '-name', label: 'По имени: Я–А' },
]

function getCustomerName(customer: CustomerListItem) {
  return customer.fullName || `Клиент #${customer.id}`
}

function CustomerMobileCard({ customer }: { customer: CustomerListItem }) {
  return (
    <article className="property-mobile-card customer-mobile-card">
      <div className="property-mobile-card__heading">
        <div>
          <span>{customer.residenceCity || 'Город не указан'}</span>
          <h2>{getCustomerName(customer)}</h2>
        </div>
        <span
          className={
            `customer-status ${customer.isActive ? '' : 'customer-status--inactive'}`
          }
        >
          {customer.isActive ? 'Активен' : 'Неактивен'}
        </span>
      </div>
      <dl>
        <div><dt>Телефон</dt><dd>{customer.phone || '—'}</dd></div>
        <div><dt>Email</dt><dd>{customer.email || '—'}</dd></div>
        <div>
          <dt>Добавлен</dt>
          <dd>{formatDateTime(customer.createdAt)}</dd>
        </div>
      </dl>
      <Link className="text-link" to={`/customers/${customer.id}`}>
        Открыть карточку <span aria-hidden="true">→</span>
      </Link>
    </article>
  )
}

export function CustomerListPage() {
  useDocumentTitle('Клиенты')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const sessionQuery = useQuery(sessionQueryOptions)
  const customerQuery = useQuery({
    ...customerListQueryOptions(searchParameters),
    enabled: sessionQuery.data?.isAuthenticated === true,
  })

  const updateParameters = (updates: Record<string, string | null>) => {
    const nextParameters = new URLSearchParams(searchParameters)
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) nextParameters.delete(key)
      else nextParameters.set(key, value)
    })
    setSearchParameters(nextParameters)
  }

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const searchInput = event.currentTarget.elements.namedItem('q')
    const searchValue = searchInput instanceof HTMLInputElement
      ? searchInput.value.trim()
      : ''
    updateParameters({ q: searchValue || null, page: null })
  }

  if (sessionQuery.isLoading) return <PageLoadingState />

  if (!sessionQuery.data?.isAuthenticated) {
    return (
      <div className="page-stack">
        <header className="page-header">
          <div>
            <span className="eyebrow">Личный раздел</span>
            <h1>Клиенты</h1>
          </div>
        </header>
        <EmptyState
          title="Войдите, чтобы открыть список клиентов"
          description="Контактные и финансовые данные доступны только авторизованному владельцу."
          action={(
            <a
              className="button button--primary"
              href={`/users/login/?next=${encodeURIComponent('/app/customers')}`}
            >
              Войти
            </a>
          )}
        />
      </div>
    )
  }

  if (customerQuery.isLoading) return <PageLoadingState />
  if (customerQuery.isError || !customerQuery.data) {
    return <ErrorState onRetry={() => void customerQuery.refetch()} />
  }

  const { results, page, totalCount, totalPages } = customerQuery.data
  const ordering = searchParameters.get('ordering') ?? '-createdAt'

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Работа с клиентами</span>
          <h1>Клиенты</h1>
          <p>
            Контакты, параметры запроса и предварительная оценка покупательной
            способности в одном разделе.
          </p>
        </div>
        <div className="page-header__actions">
          <a className="button button--secondary" href="/customers/">
            Прежняя версия
          </a>
          <a className="button button--primary" href="/customers/create/">
            Добавить клиента
          </a>
        </div>
      </header>

      <section className="filter-panel" aria-label="Фильтры клиентов">
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <label htmlFor="customer-search">Поиск по клиентам</label>
          <div className="search-control">
            <span aria-hidden="true">⌕</span>
            <input
              id="customer-search"
              name="q"
              type="search"
              key={searchParameters.get('q') ?? ''}
              defaultValue={searchParameters.get('q') ?? ''}
              placeholder="Имя, телефон или email"
            />
            <button className="button button--dark" type="submit">Найти</button>
          </div>
        </form>
        <div className="sort-control">
          <label htmlFor="customer-ordering">Сортировка</label>
          <select
            id="customer-ordering"
            value={ordering}
            onChange={(event) => updateParameters({
              ordering: event.target.value,
              page: null,
            })}
          >
            {orderingOptions.map((option) => (
              <option value={option.value} key={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </section>

      <div className="results-heading" aria-live="polite">
        <p>Клиентов: <strong>{formatInteger(totalCount)}</strong></p>
        {customerQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>

      {results.length === 0 ? (
        <EmptyState
          title={searchParameters.get('q')
            ? 'По вашему запросу ничего не найдено'
            : 'Клиентов пока нет'}
          description={searchParameters.get('q')
            ? 'Измените поисковую фразу или сбросьте фильтры.'
            : 'Добавьте первого клиента, чтобы сохранить его запрос и бюджет.'}
          action={searchParameters.get('q') ? (
            <button
              className="button button--secondary"
              type="button"
              onClick={() => setSearchParameters({})}
            >
              Сбросить фильтры
            </button>
          ) : (
            <a className="button button--primary" href="/customers/create/">
              Добавить клиента
            </a>
          )}
        />
      ) : (
        <>
          <div className="table-card property-table-wrapper">
            <table className="property-table customer-table">
              <caption className="visually-hidden">Список клиентов</caption>
              <thead>
                <tr>
                  <th scope="col">Клиент</th>
                  <th scope="col">Телефон</th>
                  <th scope="col">Email</th>
                  <th scope="col">Город</th>
                  <th scope="col">Добавлен</th>
                  <th scope="col">Статус</th>
                  <th scope="col">
                    <span className="visually-hidden">Действия</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {results.map((customer) => (
                  <tr key={customer.id}>
                    <td><strong>{getCustomerName(customer)}</strong></td>
                    <td>{customer.phone || '—'}</td>
                    <td>{customer.email || '—'}</td>
                    <td>{customer.residenceCity || '—'}</td>
                    <td>{formatDateTime(customer.createdAt)}</td>
                    <td>
                      <span
                        className={
                          `customer-status ${customer.isActive
                            ? ''
                            : 'customer-status--inactive'}`
                        }
                      >
                        {customer.isActive ? 'Активен' : 'Неактивен'}
                      </span>
                    </td>
                    <td>
                      <Link
                        className="row-action"
                        to={`/customers/${customer.id}`}
                        aria-label={`Открыть карточку: ${getCustomerName(customer)}`}
                      >
                        →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="property-mobile-list">
            {results.map((customer) => (
              <CustomerMobileCard customer={customer} key={customer.id} />
            ))}
          </div>
        </>
      )}

      {totalPages > 1 ? (
        <nav className="pagination" aria-label="Страницы списка клиентов">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => updateParameters({ page: String(page - 1) })}
          >
            <span aria-hidden="true">←</span> Назад
          </button>
          <span>Страница <strong>{page}</strong> из {totalPages}</span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => updateParameters({ page: String(page + 1) })}
          >
            Далее <span aria-hidden="true">→</span>
          </button>
        </nav>
      ) : null}
    </div>
  )
}
