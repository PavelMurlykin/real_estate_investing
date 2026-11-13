import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { Pagination } from '@/shared/ui/Pagination'
import { ResetFilters } from '@/shared/ui/ResetFilters'
import { SortableHeader } from '@/shared/ui/SortableHeader'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import { propertyListQueryOptions, sessionQueryOptions } from '@/api/queries'
import type { PropertyListItem } from '@/api/schemas'
import { PropertyFilters } from '@/features/property/PropertyFilters'
import { useTableParameters } from '@/shared/lib/useTableParameters'
import { formatArea, formatCurrency, formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

function PropertyMobileCard({
  property,
  customerIdentifier,
}: {
  property: PropertyListItem
  customerIdentifier: number | null
}) {
  const customerQuery = customerIdentifier
    ? `?customerId=${customerIdentifier}`
    : ''
  const customerMortgageParameter = customerIdentifier
    ? `&customerId=${customerIdentifier}`
    : ''
  return (
    <article className="property-mobile-card">
      <div className="property-mobile-card__heading">
        <div>
          <span>{property.city}</span>
          <h2>{property.realEstateComplex}</h2>
        </div>
        <strong>{formatCurrency(property.propertyCost)}</strong>
      </div>
      <dl>
        <div>
          <dt>Корпус / квартира</dt>
          <dd>{property.building} / {property.apartmentNumber}</dd>
        </div>
        <div><dt>Планировка</dt><dd>{property.layout}</dd></div>
        <div><dt>Площадь</dt><dd>{formatArea(property.area)}</dd></div>
        <div><dt>Этаж</dt><dd>{property.floor}</dd></div>
      </dl>
      <div className="property-mobile-card__actions">
        <Link className="text-link" to={`/properties/${property.id}${customerQuery}`}>
          Подробнее <span aria-hidden="true">→</span>
        </Link>
        <Link
          className="text-link"
          to={`/mortgage?propertyId=${property.id}&propertyCost=${encodeURIComponent(property.propertyCost)}${customerMortgageParameter}`}
        >
          Рассчитать ипотеку
        </Link>
      </div>
    </article>
  )
}

export function PropertyListPage() {
  useDocumentTitle('Объекты недвижимости')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const rawCustomerIdentifier = Number(searchParameters.get('customerId'))
  const customerIdentifier = Number.isInteger(rawCustomerIdentifier)
    && rawCustomerIdentifier > 0
    ? rawCustomerIdentifier
    : null
  const customerQuery = customerIdentifier
    ? `?customerId=${customerIdentifier}`
    : ''
  const customerMortgageParameter = customerIdentifier
    ? `&customerId=${customerIdentifier}`
    : ''
  const sessionQuery = useQuery(sessionQueryOptions)
  const tableParameters = useTableParameters(searchParameters)
  const propertyQuery = useQuery(propertyListQueryOptions(tableParameters))

  const updateParameters = (updates: Record<string, string | null>) => {
    const nextParameters = new URLSearchParams(searchParameters)
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) {
        nextParameters.delete(key)
      } else {
        nextParameters.set(key, value)
      }
    })
    setSearchParameters(nextParameters)
  }

  if (propertyQuery.isLoading) {
    return <PageLoadingState />
  }

  if (propertyQuery.isError || !propertyQuery.data) {
    return <ErrorState onRetry={() => void propertyQuery.refetch()} />
  }

  const { results, page, totalCount, totalPages } = propertyQuery.data


  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Каталог</span>
          <h1>Объекты недвижимости</h1>
          <p>
            {customerIdentifier
              ? 'Выберите объект для нового расчёта клиента.'
              : 'Подберите объект по адресу, застройщику, жилому комплексу или номеру квартиры.'}
          </p>
        </div>
        {customerIdentifier ? (
          <Link className="button button--secondary" to={`/customers/${customerIdentifier}`}>
            К карточке клиента
          </Link>
        ) : sessionQuery.data?.capabilities.manageCatalogs ? (
          <Link className="button button--primary" to="/properties/new">
            Добавить объект
          </Link>
        ) : null}
      </header>

      <section className="filter-panel" aria-label="Фильтры объектов">
        <PropertyFilters />
        {searchParameters.get('search') ? <p className="filter-panel__notice">
          Поиск из ссылки: {searchParameters.get('search')}{' '}
          <button type="button" className="text-button" aria-label="Убрать поиск из ссылки"
            onClick={() => updateParameters({ search: null, page: null })}>Убрать</button>
        </p> : null}
        <ResetFilters />
      </section>

      <div className="results-heading" aria-live="polite">
        <p>Найдено объектов: <strong>{formatInteger(totalCount)}</strong></p>
        {propertyQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>

      {results.length === 0 ? (
        <EmptyState
          title="По вашему запросу ничего не найдено"
          description="Измените значения фильтров или нажмите «Сбросить»."
        />
      ) : (
        <>
          <TableScrollArea className="table-card property-table-wrapper" label="Список объектов недвижимости">
            <table className="property-table">
              <caption className="visually-hidden">
                Список объектов недвижимости
              </caption>
              <thead>
                <tr>
                  <SortableHeader field="city" defaultOrdering="city">Город</SortableHeader>
                  <SortableHeader field="developer" defaultOrdering="city">Застройщик</SortableHeader>
                  <SortableHeader field="realEstateComplex" defaultOrdering="city">ЖК</SortableHeader>
                  <SortableHeader field="building" defaultOrdering="city">Корпус</SortableHeader>
                  <SortableHeader field="apartmentNumber" defaultOrdering="city">Квартира</SortableHeader>
                  <SortableHeader field="layout" defaultOrdering="city">Планировка</SortableHeader>
                  <SortableHeader field="area" defaultOrdering="city">Площадь</SortableHeader>
                  <SortableHeader field="propertyCost" defaultOrdering="city">Стоимость</SortableHeader>
                  <th scope="col"><span className="visually-hidden">Действия</span></th>
                </tr>
              </thead>
              <tbody>
                {results.map((property) => (
                  <tr key={property.id}>
                    <td>{property.city}</td>
                    <td>{property.developer}</td>
                    <td><strong>{property.realEstateComplex}</strong></td>
                    <td>{property.building}</td>
                    <td>{property.apartmentNumber}</td>
                    <td>{property.layout}</td>
                    <td>{formatArea(property.area)}</td>
                    <td><strong>{formatCurrency(property.propertyCost)}</strong></td>
                    <td>
                      <div className="row-actions">
                        <Link
                          className="row-action"
                          to={`/properties/${property.id}${customerQuery}`}
                          aria-label={`Открыть квартиру ${property.apartmentNumber}`}
                        >
                          →
                        </Link>
                        <Link
                          className="row-action row-action--calculator"
                          to={`/mortgage?propertyId=${property.id}&propertyCost=${encodeURIComponent(property.propertyCost)}${customerMortgageParameter}`}
                          aria-label={`Рассчитать ипотеку для квартиры ${property.apartmentNumber}`}
                        >
                          ₽
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScrollArea>
          <div className="property-mobile-list">
            {results.map((property) => (
              <PropertyMobileCard
                property={property}
                customerIdentifier={customerIdentifier}
                key={property.id}
              />
            ))}
          </div>
        </>
      )}

      {totalPages > 1 ? (
        <Pagination label="Страницы каталога" page={page} totalPages={totalPages} onPageChange={(nextPage) => updateParameters({ page: String(nextPage) })} />
      ) : null}
    </div>
  )
}
