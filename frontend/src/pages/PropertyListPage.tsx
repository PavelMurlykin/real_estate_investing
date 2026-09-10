import { useQuery } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { propertyListQueryOptions, sessionQueryOptions } from '@/api/queries'
import type { PropertyListItem } from '@/api/schemas'
import { formatArea, formatCurrency, formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

const orderingOptions = [
  { value: 'city', label: 'Городу: А–Я' },
  { value: '-city', label: 'Городу: Я–А' },
  { value: 'realEstateComplex', label: 'ЖК: А–Я' },
  { value: '-realEstateComplex', label: 'ЖК: Я–А' },
  { value: 'area', label: 'Площади: сначала меньше' },
  { value: '-area', label: 'Площади: сначала больше' },
  { value: 'propertyCost', label: 'Цене: сначала дешевле' },
  { value: '-propertyCost', label: 'Цене: сначала дороже' },
]

function PropertyMobileCard({ property }: { property: PropertyListItem }) {
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
        <Link className="text-link" to={`/properties/${property.id}`}>
          Подробнее <span aria-hidden="true">→</span>
        </Link>
        <Link
          className="text-link"
          to={`/mortgage?propertyId=${property.id}&propertyCost=${encodeURIComponent(property.propertyCost)}`}
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
  const sessionQuery = useQuery(sessionQueryOptions)
  const propertyQuery = useQuery(propertyListQueryOptions(searchParameters))

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

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const searchInput = event.currentTarget.elements.namedItem('search')
    const searchValue = searchInput instanceof HTMLInputElement
      ? searchInput.value.trim()
      : ''
    updateParameters({ search: searchValue || null, page: null })
  }

  if (propertyQuery.isLoading) {
    return <PageLoadingState />
  }

  if (propertyQuery.isError || !propertyQuery.data) {
    return <ErrorState onRetry={() => void propertyQuery.refetch()} />
  }

  const { results, page, totalCount, totalPages } = propertyQuery.data
  const ordering = searchParameters.get('ordering') ?? 'city'

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Каталог</span>
          <h1>Объекты недвижимости</h1>
          <p>
            Подберите объект по адресу, застройщику, жилому комплексу или
            номеру квартиры.
          </p>
        </div>
        {sessionQuery.data?.capabilities.manageCatalogs ? (
          <a className="button button--primary" href="/property/create/">
            Добавить объект
          </a>
        ) : null}
      </header>

      <section className="filter-panel" aria-label="Фильтры объектов">
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <label htmlFor="property-search">Поиск по каталогу</label>
          <div className="search-control">
            <span aria-hidden="true">⌕</span>
            <input
              id="property-search"
              name="search"
              type="search"
              key={searchParameters.get('search') ?? ''}
              defaultValue={searchParameters.get('search') ?? ''}
              placeholder="Город, ЖК, застройщик, корпус или квартира"
            />
            <button className="button button--dark" type="submit">
              Найти
            </button>
          </div>
        </form>
        <div className="sort-control">
          <label htmlFor="property-ordering">Сортировка</label>
          <select
            id="property-ordering"
            value={ordering}
            onChange={(event) =>
              updateParameters({ ordering: event.target.value, page: null })
            }
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
        <p>Найдено объектов: <strong>{formatInteger(totalCount)}</strong></p>
        {propertyQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>

      {results.length === 0 ? (
        <EmptyState
          title="По вашему запросу ничего не найдено"
          description="Измените поисковую фразу или сбросьте фильтры."
          action={
            <button
              className="button button--secondary"
              type="button"
              onClick={() => setSearchParameters({})}
            >
              Сбросить фильтры
            </button>
          }
        />
      ) : (
        <>
          <div className="table-card property-table-wrapper">
            <table className="property-table">
              <caption className="visually-hidden">
                Список объектов недвижимости
              </caption>
              <thead>
                <tr>
                  <th scope="col">Город</th>
                  <th scope="col">Застройщик</th>
                  <th scope="col">ЖК</th>
                  <th scope="col">Корпус</th>
                  <th scope="col">Квартира</th>
                  <th scope="col">Планировка</th>
                  <th scope="col">Площадь</th>
                  <th scope="col">Стоимость</th>
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
                          to={`/properties/${property.id}`}
                          aria-label={`Открыть квартиру ${property.apartmentNumber}`}
                        >
                          →
                        </Link>
                        <Link
                          className="row-action row-action--calculator"
                          to={`/mortgage?propertyId=${property.id}&propertyCost=${encodeURIComponent(property.propertyCost)}`}
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
          </div>
          <div className="property-mobile-list">
            {results.map((property) => (
              <PropertyMobileCard property={property} key={property.id} />
            ))}
          </div>
        </>
      )}

      {totalPages > 1 ? (
        <nav className="pagination" aria-label="Страницы каталога">
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
