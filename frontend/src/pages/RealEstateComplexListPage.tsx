import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  deleteRealEstateComplex,
  realEstateComplexListQueryOptions,
  realEstateComplexOptionsQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type { RealEstateComplexListItem } from '@/api/schemas'
import { formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

const orderingOptions = [
  { value: 'developer', label: 'По застройщику' },
  { value: 'name', label: 'По названию: А–Я' },
  { value: '-name', label: 'По названию: Я–А' },
  { value: 'city', label: 'По городу' },
  { value: '-buildingCount', label: 'Сначала больше корпусов' },
]

export function RealEstateComplexListPage() {
  useDocumentTitle('Жилые комплексы')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const sessionQuery = useQuery(sessionQueryOptions)
  const complexQuery = useQuery(
    realEstateComplexListQueryOptions(searchParameters),
  )
  const optionsQuery = useQuery(
    realEstateComplexOptionsQueryOptions({ regionId: null, cityId: null }),
  )
  const queryClient = useQueryClient()
  const [selectedComplex, setSelectedComplex] = (
    useState<RealEstateComplexListItem | null>(null)
  )
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: (complexIdentifier: number) => (
      deleteRealEstateComplex(complexIdentifier)
    ),
    onSuccess: async () => {
      setSelectedComplex(null)
      await queryClient.invalidateQueries({
        queryKey: ['real-estate-complexes'],
      })
      await queryClient.invalidateQueries({ queryKey: ['overview'] })
      window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
    },
  })

  useEffect(() => {
    if (!selectedComplex) return
    cancelButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleteMutation.isPending) {
        setSelectedComplex(null)
        window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [deleteMutation.isPending, selectedComplex])

  const updateParameters = (updates: Record<string, string | null>) => {
    const nextParameters = new URLSearchParams(searchParameters)
    Object.entries(updates).forEach(([fieldName, value]) => {
      if (!value || value === 'all') nextParameters.delete(fieldName)
      else nextParameters.set(fieldName, value)
    })
    setSearchParameters(nextParameters)
  }

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const searchInput = event.currentTarget.elements.namedItem('search')
    const search = searchInput instanceof HTMLInputElement
      ? searchInput.value.trim()
      : ''
    updateParameters({ search: search || null, page: null })
  }

  const openDeleteDialog = (
    realEstateComplex: RealEstateComplexListItem,
    trigger: HTMLButtonElement,
  ) => {
    deleteMutation.reset()
    deleteTriggerRef.current = trigger
    setSelectedComplex(realEstateComplex)
  }

  const closeDeleteDialog = () => {
    if (deleteMutation.isPending) return
    setSelectedComplex(null)
    window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
  }

  if (complexQuery.isLoading) return <PageLoadingState />
  if (complexQuery.isError || !complexQuery.data) {
    return <ErrorState onRetry={() => void complexQuery.refetch()} />
  }

  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  const options = optionsQuery.data
  const { results, page, totalCount, totalPages } = complexQuery.data

  return (
    <div className="page-stack complex-list-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Недвижимость</span>
          <h1>Жилые комплексы</h1>
          <p>
            Проекты застройщиков, корпуса, сроки ввода и транспортная
            доступность.
          </p>
        </div>
        <div className="page-header__actions">
          <a className="button button--secondary" href="/property/complexes/">
            Прежняя версия
          </a>
          {canManageCatalogs ? (
            <Link className="button button--primary" to="/complexes/new">
              Добавить ЖК
            </Link>
          ) : null}
        </div>
      </header>

      <section
        className="filter-panel complex-filter-panel"
        aria-label="Фильтры жилых комплексов"
      >
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <label htmlFor="complex-search">Поиск</label>
          <div className="search-control">
            <span aria-hidden="true">⌕</span>
            <input
              id="complex-search"
              name="search"
              type="search"
              key={searchParameters.get('search') ?? ''}
              defaultValue={searchParameters.get('search') ?? ''}
              placeholder="ЖК, застройщик или город"
            />
            <button className="button button--dark" type="submit">
              Найти
            </button>
          </div>
        </form>
        <div className="sort-control">
          <label htmlFor="complex-developer">Застройщик</label>
          <select
            id="complex-developer"
            value={searchParameters.get('developerId') ?? ''}
            onChange={(event) => updateParameters({
              developerId: event.target.value || null,
              page: null,
            })}
          >
            <option value="">Все застройщики</option>
            {options?.developers.map((developer) => (
              <option key={developer.id} value={developer.id}>
                {developer.label}
              </option>
            ))}
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="complex-city">Город</label>
          <select
            id="complex-city"
            value={searchParameters.get('cityId') ?? ''}
            onChange={(event) => updateParameters({
              cityId: event.target.value || null,
              page: null,
            })}
          >
            <option value="">Все города</option>
            {options?.cities.map((city) => (
              <option key={city.id} value={city.id}>{city.name}</option>
            ))}
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="complex-class">Класс</label>
          <select
            id="complex-class"
            value={searchParameters.get('realEstateClassId') ?? ''}
            onChange={(event) => updateParameters({
              realEstateClassId: event.target.value || null,
              page: null,
            })}
          >
            <option value="">Все классы</option>
            {options?.realEstateClasses.map((complexClass) => (
              <option key={complexClass.id} value={complexClass.id}>
                {complexClass.name}
              </option>
            ))}
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="complex-type">Тип</label>
          <select
            id="complex-type"
            value={searchParameters.get('realEstateTypeId') ?? ''}
            onChange={(event) => updateParameters({
              realEstateTypeId: event.target.value || null,
              page: null,
            })}
          >
            <option value="">Все типы</option>
            {options?.realEstateTypes.map((complexType) => (
              <option key={complexType.id} value={complexType.id}>
                {complexType.name}
              </option>
            ))}
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="complex-status">Статус</label>
          <select
            id="complex-status"
            value={searchParameters.get('status') ?? 'all'}
            onChange={(event) => updateParameters({
              status: event.target.value,
              page: null,
            })}
          >
            <option value="all">Все</option>
            <option value="active">Активные</option>
            <option value="inactive">Неактивные</option>
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="complex-ordering">Сортировка</label>
          <select
            id="complex-ordering"
            value={searchParameters.get('ordering') ?? 'developer'}
            onChange={(event) => updateParameters({
              ordering: event.target.value,
              page: null,
            })}
          >
            {orderingOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </section>

      <div className="results-heading" aria-live="polite">
        <p>Жилых комплексов: <strong>{formatInteger(totalCount)}</strong></p>
        {complexQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>

      {results.length === 0 ? (
        <EmptyState
          title="Жилые комплексы не найдены"
          description="Измените фильтры или добавьте новый жилой комплекс."
          action={canManageCatalogs ? (
            <Link className="button button--primary" to="/complexes/new">
              Добавить ЖК
            </Link>
          ) : undefined}
        />
      ) : (
        <>
          <div className="table-card property-table-wrapper">
            <table className="property-table catalog-table complex-table">
              <caption className="visually-hidden">
                Список жилых комплексов
              </caption>
              <thead>
                <tr>
                  <th scope="col">Жилой комплекс</th>
                  <th scope="col">Застройщик</th>
                  <th scope="col">Город</th>
                  <th scope="col">Класс</th>
                  <th scope="col">Тип</th>
                  <th scope="col">Корпусов</th>
                  <th scope="col"><span className="visually-hidden">Действия</span></th>
                </tr>
              </thead>
              <tbody>
                {results.map((realEstateComplex) => (
                  <tr key={realEstateComplex.id}>
                    <td>
                      <Link
                        className="text-link"
                        to={`/complexes/${realEstateComplex.id}`}
                      >
                        {realEstateComplex.name}
                      </Link>
                      {!realEstateComplex.isActive ? (
                        <span className="catalog-status catalog-status--inactive">
                          Неактивен
                        </span>
                      ) : null}
                    </td>
                    <td>{realEstateComplex.developer.label}</td>
                    <td>{realEstateComplex.city}</td>
                    <td>{realEstateComplex.realEstateClass}</td>
                    <td>{realEstateComplex.realEstateType}</td>
                    <td>{formatInteger(realEstateComplex.buildingCount)}</td>
                    <td>
                      <div className="row-actions">
                        <Link
                          className="row-action"
                          to={`/complexes/${realEstateComplex.id}`}
                          aria-label={`Открыть: ${realEstateComplex.name}`}
                        >
                          →
                        </Link>
                        {canManageCatalogs ? (
                          <>
                            <Link
                              className="row-action"
                              to={`/complexes/${realEstateComplex.id}/edit`}
                              aria-label={`Редактировать: ${realEstateComplex.name}`}
                            >
                              ✎
                            </Link>
                            <button
                              className="row-action row-action--danger"
                              type="button"
                              aria-label={`Удалить: ${realEstateComplex.name}`}
                              onClick={(event) => openDeleteDialog(
                                realEstateComplex,
                                event.currentTarget,
                              )}
                            >
                              ×
                            </button>
                          </>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="property-mobile-list">
            {results.map((realEstateComplex) => (
              <article
                className="property-mobile-card catalog-mobile-card"
                key={realEstateComplex.id}
              >
                <div className="property-mobile-card__heading">
                  <div>
                    <span>{realEstateComplex.city}</span>
                    <h2>{realEstateComplex.name}</h2>
                  </div>
                  <span className={realEstateComplex.isActive
                    ? 'catalog-status'
                    : 'catalog-status catalog-status--inactive'}
                  >
                    {realEstateComplex.isActive ? 'Активен' : 'Неактивен'}
                  </span>
                </div>
                <dl>
                  <div><dt>Застройщик</dt><dd>{realEstateComplex.developer.label}</dd></div>
                  <div><dt>Класс и тип</dt><dd>{realEstateComplex.realEstateClass}, {realEstateComplex.realEstateType}</dd></div>
                  <div><dt>Корпусов</dt><dd>{realEstateComplex.buildingCount}</dd></div>
                </dl>
                <div className="property-mobile-card__actions">
                  <Link className="text-link" to={`/complexes/${realEstateComplex.id}`}>
                    Подробнее
                  </Link>
                  {canManageCatalogs ? (
                    <Link className="text-link" to={`/complexes/${realEstateComplex.id}/edit`}>
                      Редактировать
                    </Link>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </>
      )}

      {totalPages > 1 ? (
        <nav className="pagination" aria-label="Страницы жилых комплексов">
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

      {selectedComplex ? (
        <div
          className="confirmation-dialog-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) closeDeleteDialog()
          }}
        >
          <section
            className="confirmation-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="complex-delete-title"
            aria-describedby="complex-delete-description"
          >
            <span className="eyebrow">Подтверждение</span>
            <h2 id="complex-delete-title">Удалить жилой комплекс?</h2>
            <p id="complex-delete-description">
              «{selectedComplex.name}» и его служебные данные будут удалены.
            </p>
            {deleteMutation.isError ? (
              <p className="form-error" role="alert">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'Сначала удалите или переназначьте связанные объекты недвижимости.'
                  : 'Не удалось удалить жилой комплекс. Повторите попытку.'}
              </p>
            ) : null}
            <div className="confirmation-dialog__actions">
              <button
                className="button button--secondary"
                type="button"
                ref={cancelButtonRef}
                disabled={deleteMutation.isPending}
                onClick={closeDeleteDialog}
              >
                Отмена
              </button>
              <button
                className="button button--danger"
                type="button"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(selectedComplex.id)}
              >
                {deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}
