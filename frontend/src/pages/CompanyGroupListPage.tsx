import { Notice } from '@/shared/ui/Notice'
import { restoreFocus } from '@/shared/lib/restoreFocus'
import { ModalDialog } from '@/shared/ui/ModalDialog'
import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { Pagination } from '@/shared/ui/Pagination'
import { ResetFilters } from '@/shared/ui/ResetFilters'
import { useTableParameters } from '@/shared/lib/useTableParameters'
import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { SortableHeader } from '@/shared/ui/SortableHeader'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  companyGroupListQueryOptions,
  deleteCompanyGroup,
  sessionQueryOptions,
} from '@/api/queries'
import type { CompanyGroup } from '@/api/schemas'
import { formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

export function CompanyGroupListPage() {
  useDocumentTitle('Группы компаний')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const tableParameters = useTableParameters(searchParameters)
  const sessionQuery = useQuery(sessionQueryOptions)
  const companyGroupQuery = useQuery(
    companyGroupListQueryOptions(tableParameters),
  )
  const queryClient = useQueryClient()
  const [selectedCompanyGroup, setSelectedCompanyGroup] = (
    useState<CompanyGroup | null>(null)
  )
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: (companyGroupIdentifier: number) => (
      deleteCompanyGroup(companyGroupIdentifier)
    ),
    onSuccess: async () => {
      setSelectedCompanyGroup(null)
      await queryClient.invalidateQueries({ queryKey: ['company-groups'] })
      window.setTimeout(() => restoreFocus(deleteTriggerRef.current), 0)
    },
  })

  const updateParameters = (updates: Record<string, string | null>) => {
    const nextParameters = new URLSearchParams(searchParameters)
    Object.entries(updates).forEach(([fieldName, value]) => {
      if (!value) nextParameters.delete(fieldName)
      else nextParameters.set(fieldName, value)
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

  const openDeleteDialog = (
    companyGroup: CompanyGroup,
    trigger: HTMLButtonElement,
  ) => {
    deleteMutation.reset()
    deleteTriggerRef.current = trigger
    setSelectedCompanyGroup(companyGroup)
  }

  const closeDeleteDialog = () => {
    if (deleteMutation.isPending) return
    setSelectedCompanyGroup(null)
    window.setTimeout(() => restoreFocus(deleteTriggerRef.current), 0)
  }

  if (companyGroupQuery.isLoading) return <PageLoadingState />
  if (companyGroupQuery.isError || !companyGroupQuery.data) {
    return <ErrorState onRetry={() => companyGroupQuery.refetch()} />
  }

  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  const { results, page, totalCount, totalPages } = companyGroupQuery.data

  return (
    <div className="page-stack company-group-list-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Недвижимость</span>
          <h1>Группы компаний</h1>
          <p>
            Базовый справочник для объединения застройщиков в корпоративные
            группы.
          </p>
        </div>
        {canManageCatalogs ? (
          <div className="page-header__actions">
            <Link className="button button--primary" to="/company-groups/new">
              Добавить группу
            </Link>
          </div>
        ) : null}
      </header>

      <section className="filter-panel" aria-label="Фильтры групп компаний">
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <div className="live-search-control">
            <LiveFilterInput label="Поиск по названию" id="company-group-search" parameter="q" placeholder="Например, Группа Север" />
            <button className="button button--dark" type="submit">Найти</button>
          </div>
        </form>
        <ResetFilters />
      </section>

      <div className="results-heading" aria-live="polite">
        <p>
          Групп компаний: <strong>{formatInteger(totalCount)}</strong>
        </p>
        {companyGroupQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>

      {results.length === 0 ? (
        <EmptyState
          title={searchParameters.get('q')
            ? 'По вашему запросу ничего не найдено'
            : 'Групп компаний пока нет'}
          description={searchParameters.get('q')
            ? 'Измените название или сбросьте фильтр.'
            : 'Добавьте первую группу, чтобы привязать к ней застройщиков.'}
          action={searchParameters.get('q') ? null : canManageCatalogs ? (
            <Link className="button button--primary" to="/company-groups/new">
              Добавить группу
            </Link>
          ) : undefined}
        />
      ) : (
        <>
          <TableScrollArea className="table-card property-table-wrapper" label="Список групп компаний">
            <table className="property-table catalog-table">
              <caption className="visually-hidden">
                Список групп компаний
              </caption>
              <thead>
                <tr>
                  <SortableHeader field="name" defaultOrdering="name">Название</SortableHeader>
                  <SortableHeader field="developerCount" defaultOrdering="name">Застройщиков</SortableHeader>
                  {canManageCatalogs ? (
                    <th scope="col">
                      <span className="visually-hidden">Действия</span>
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {results.map((companyGroup) => (
                  <tr key={companyGroup.id}>
                    <td><strong>{companyGroup.name}</strong></td>
                    <td>{formatInteger(companyGroup.developerCount)}</td>
                    {canManageCatalogs ? (
                      <td>
                        <div className="row-actions">
                          <Link
                            className="row-action"
                            to={`/company-groups/${companyGroup.id}/edit`}
                            aria-label={`Редактировать: ${companyGroup.name}`}
                          >
                            ✎
                          </Link>
                          <button
                            className="row-action row-action--danger"
                            type="button"
                            aria-label={`Удалить: ${companyGroup.name}`}
                            onClick={(event) => openDeleteDialog(
                              companyGroup,
                              event.currentTarget,
                            )}
                          >
                            ×
                          </button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScrollArea>
          <div className="property-mobile-list">
            {results.map((companyGroup) => (
              <article
                className="property-mobile-card catalog-mobile-card"
                key={companyGroup.id}
              >
                <div className="property-mobile-card__heading">
                  <div>
                    <span>Группа компаний</span>
                    <h2>{companyGroup.name}</h2>
                  </div>
                </div>
                <dl>
                  <div>
                    <dt>Застройщиков</dt>
                    <dd>{formatInteger(companyGroup.developerCount)}</dd>
                  </div>
                </dl>
                {canManageCatalogs ? (
                  <div className="property-mobile-card__actions">
                    <Link
                      className="text-link"
                      to={`/company-groups/${companyGroup.id}/edit`}
                    >
                      Редактировать
                    </Link>
                    <button
                      className="text-button text-button--danger"
                      type="button"
                      onClick={(event) => openDeleteDialog(
                        companyGroup,
                        event.currentTarget,
                      )}
                    >
                      Удалить
                    </button>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </>
      )}

      {totalPages > 1 ? (
        <Pagination label="Страницы групп компаний" page={page} totalPages={totalPages} onPageChange={(nextPage) => updateParameters({ page: String(nextPage) })} />
      ) : null}

      {selectedCompanyGroup ? (
        <ModalDialog labelledBy="company-group-delete-title" describedBy="company-group-delete-description" pending={deleteMutation.isPending} onClose={closeDeleteDialog}>
            <span className="eyebrow">Подтверждение</span>
            <h2 id="company-group-delete-title">Удалить группу компаний?</h2>
            <p id="company-group-delete-description">
              «{selectedCompanyGroup.name}» будет удалена без возможности
              восстановления.
            </p>
            {deleteMutation.isError ? (
              <Notice as="p" tone="error" role="alert" className="form-error">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'Сначала отвяжите от группы всех застройщиков.'
                  : 'Не удалось удалить группу. Повторите попытку.'}
              </Notice>
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
                onClick={() => deleteMutation.mutate(
                  selectedCompanyGroup.id,
                )}
              >
                {deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}
              </button>
            </div>
          </ModalDialog>
      ) : null}
    </div>
  )
}
