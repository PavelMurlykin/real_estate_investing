import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { Pagination } from '@/shared/ui/Pagination'
import { ComplexImport } from '@/features/realEstateComplex/ComplexImport'
import { ResetFilters } from '@/shared/ui/ResetFilters'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'
import { useTableParameters } from '@/shared/lib/useTableParameters'
import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { SortableHeader } from '@/shared/ui/SortableHeader'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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

export function RealEstateComplexListPage() {
  useDocumentTitle('Жилые комплексы')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const tableParameters = useTableParameters(searchParameters)
  const sessionQuery = useQuery(sessionQueryOptions)
  const complexQuery = useQuery(
    realEstateComplexListQueryOptions(tableParameters),
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
        {canManageCatalogs ? (
          <div className="page-header__actions">
            <Link className="button button--primary" to="/complexes/new">
              Добавить ЖК
            </Link>
          </div>
        ) : null}
      </header>

      {sessionQuery.data?.capabilities.syncExternalData ? <ComplexImport /> : null}

      <section
        className="filter-panel complex-filter-panel"
        aria-label="Фильтры жилых комплексов"
      >
        <form className="search-form" role="search" onSubmit={(event) => event.preventDefault()}>
          <div className="live-search-control">
            <LiveFilterInput label="Поиск" id="complex-search" parameter="search" placeholder="ЖК, застройщик или город" />
          </div>
        </form>
        <RemoteSelect filter dictionary="developers" label="Застройщик" value={searchParameters.get('developerId') ?? ''}
            initialOptions={options?.developers.map((option) => ({ id: option.id, label: option.label }))}
            onChange={(value) => updateParameters({
              developerId: value || null,
              page: null,
            })} />
        <RemoteSelect filter dictionary="cities" label="Город" value={searchParameters.get('cityId') ?? ''}
            initialOptions={options?.cities.map((option) => ({ id: option.id, label: option.name }))}
            onChange={(value) => updateParameters({
              cityId: value || null,
              page: null,
            })} />
        <RemoteSelect filter dictionary="real-estate-classes" label="Класс" value={searchParameters.get('realEstateClassId') ?? ''}
            initialOptions={options?.realEstateClasses.map((option) => ({ id: option.id, label: option.name }))}
            onChange={(value) => updateParameters({
              realEstateClassId: value || null,
              page: null,
            })} />
        <RemoteSelect filter dictionary="real-estate-types" label="Тип" value={searchParameters.get('realEstateTypeId') ?? ''}
            initialOptions={options?.realEstateTypes.map((option) => ({ id: option.id, label: option.name }))}
            onChange={(value) => updateParameters({
              realEstateTypeId: value || null,
              page: null,
            })} />
        <ResetFilters />
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
          <TableScrollArea className="table-card property-table-wrapper" label="Список жилых комплексов">
            <table className="property-table catalog-table complex-table">
              <caption className="visually-hidden">
                Список жилых комплексов
              </caption>
              <thead>
                <tr>
                  <SortableHeader field="name" defaultOrdering="name">Жилой комплекс</SortableHeader>
                  <SortableHeader field="developer" defaultOrdering="name">Застройщик</SortableHeader>
                  <SortableHeader field="city" defaultOrdering="name">Город</SortableHeader>
                  <SortableHeader field="realEstateClass" defaultOrdering="name">Класс</SortableHeader>
                  <SortableHeader field="realEstateType" defaultOrdering="name">Тип</SortableHeader>
                  <SortableHeader field="buildingCount" defaultOrdering="name">Корпусов</SortableHeader>
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
          </TableScrollArea>
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
        <Pagination label="Страницы жилых комплексов" page={page} totalPages={totalPages} onPageChange={(nextPage) => updateParameters({ page: String(nextPage) })} />
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
