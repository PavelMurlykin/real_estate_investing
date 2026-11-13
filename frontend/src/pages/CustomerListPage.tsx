import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { Pagination } from '@/shared/ui/Pagination'
import { ResetFilters } from '@/shared/ui/ResetFilters'
import { useTableParameters } from '@/shared/lib/useTableParameters'
import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { SortableHeader } from '@/shared/ui/SortableHeader'
import { useQuery } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import {
  customerListQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type { CustomerListItem } from '@/api/schemas'
import { formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

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

      </div>
      <dl>
        <div><dt>Телефон</dt><dd>{customer.phone || '—'}</dd></div>
        <div><dt>Email</dt><dd>{customer.email || '—'}</dd></div>

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
  const tableParameters = useTableParameters(searchParameters)
  const sessionQuery = useQuery(sessionQueryOptions)
  const customerQuery = useQuery({
    ...customerListQueryOptions(tableParameters),
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
  if (sessionQuery.isError) return <ErrorState title="Не удалось проверить вход" isRetrying={sessionQuery.isFetching} onRetry={() => sessionQuery.refetch()} />

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
              href={`/app/login?next=${encodeURIComponent('/app/customers')}`}
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
    return <ErrorState onRetry={() => customerQuery.refetch()} />
  }

  const { results, page, totalCount, totalPages } = customerQuery.data


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
          <Link className="button button--primary" to="/customers/new">
            Добавить клиента
          </Link>
        </div>
      </header>

      <section className="filter-panel" aria-label="Фильтры клиентов">
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <div className="live-search-control">
            <LiveFilterInput label="Поиск по клиентам" id="customer-search" parameter="q" placeholder="Имя, телефон или email" />
            <button className="button button--dark" type="submit">Найти</button>
          </div>
        </form>
        <ResetFilters />
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
          action={searchParameters.get('q') ? null : (
            <Link className="button button--primary" to="/customers/new">
              Добавить клиента
            </Link>
          )}
        />
      ) : (
        <>
          <TableScrollArea className="table-card property-table-wrapper" label="Список клиентов">
            <table className="property-table customer-table">
              <caption className="visually-hidden">Список клиентов</caption>
              <thead>
                <tr>
                  <SortableHeader field="name" defaultOrdering="-createdAt">Клиент</SortableHeader>
                  <SortableHeader field="phone" defaultOrdering="-createdAt">Телефон</SortableHeader>
                  <SortableHeader field="email" defaultOrdering="-createdAt">Email</SortableHeader>
                  <SortableHeader field="city" defaultOrdering="-createdAt">Город</SortableHeader>


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
          </TableScrollArea>
          <div className="property-mobile-list">
            {results.map((customer) => (
              <CustomerMobileCard customer={customer} key={customer.id} />
            ))}
          </div>
        </>
      )}

      {totalPages > 1 ? (
        <Pagination label="Страницы списка клиентов" page={page} totalPages={totalPages} onPageChange={(nextPage) => updateParameters({ page: String(nextPage) })} />
      ) : null}
    </div>
  )
}
