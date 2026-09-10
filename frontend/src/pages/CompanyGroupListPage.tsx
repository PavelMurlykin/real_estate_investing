import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
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

const orderingOptions = [
  { value: 'name', label: 'По названию: А–Я' },
  { value: '-name', label: 'По названию: Я–А' },
]

export function CompanyGroupListPage() {
  useDocumentTitle('Группы компаний')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const sessionQuery = useQuery(sessionQueryOptions)
  const companyGroupQuery = useQuery(
    companyGroupListQueryOptions(searchParameters),
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
      window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
    },
  })

  useEffect(() => {
    if (!selectedCompanyGroup) return
    cancelButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleteMutation.isPending) {
        setSelectedCompanyGroup(null)
        window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [deleteMutation.isPending, selectedCompanyGroup])

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
    window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
  }

  if (companyGroupQuery.isLoading) return <PageLoadingState />
  if (companyGroupQuery.isError || !companyGroupQuery.data) {
    return <ErrorState onRetry={() => void companyGroupQuery.refetch()} />
  }

  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  const { results, page, totalCount, totalPages } = companyGroupQuery.data
  const ordering = searchParameters.get('ordering') ?? 'name'

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
        <div className="page-header__actions">
          <a
            className="button button--secondary"
            href="/property/company-groups/"
          >
            Прежняя версия
          </a>
          {canManageCatalogs ? (
            <Link className="button button--primary" to="/company-groups/new">
              Добавить группу
            </Link>
          ) : null}
        </div>
      </header>

      <section className="filter-panel" aria-label="Фильтры групп компаний">
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <label htmlFor="company-group-search">Поиск по названию</label>
          <div className="search-control">
            <span aria-hidden="true">⌕</span>
            <input
              id="company-group-search"
              name="q"
              type="search"
              key={searchParameters.get('q') ?? ''}
              defaultValue={searchParameters.get('q') ?? ''}
              placeholder="Например, Группа Север"
            />
            <button className="button button--dark" type="submit">
              Найти
            </button>
          </div>
        </form>
        <div className="sort-control">
          <label htmlFor="company-group-ordering">Сортировка</label>
          <select
            id="company-group-ordering"
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
          action={searchParameters.get('q') ? (
            <button
              className="button button--secondary"
              type="button"
              onClick={() => setSearchParameters({})}
            >
              Сбросить фильтр
            </button>
          ) : canManageCatalogs ? (
            <Link className="button button--primary" to="/company-groups/new">
              Добавить группу
            </Link>
          ) : undefined}
        />
      ) : (
        <>
          <div className="table-card property-table-wrapper">
            <table className="property-table catalog-table">
              <caption className="visually-hidden">
                Список групп компаний
              </caption>
              <thead>
                <tr>
                  <th scope="col">Название</th>
                  <th scope="col">Застройщиков</th>
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
          </div>
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
        <nav className="pagination" aria-label="Страницы групп компаний">
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

      {selectedCompanyGroup ? (
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
            aria-labelledby="company-group-delete-title"
            aria-describedby="company-group-delete-description"
          >
            <span className="eyebrow">Подтверждение</span>
            <h2 id="company-group-delete-title">Удалить группу компаний?</h2>
            <p id="company-group-delete-description">
              «{selectedCompanyGroup.name}» будет удалена без возможности
              восстановления.
            </p>
            {deleteMutation.isError ? (
              <p className="form-error" role="alert">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'Сначала отвяжите от группы всех застройщиков.'
                  : 'Не удалось удалить группу. Повторите попытку.'}
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
                onClick={() => deleteMutation.mutate(
                  selectedCompanyGroup.id,
                )}
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
