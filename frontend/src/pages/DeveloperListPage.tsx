import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  deleteDeveloper,
  developerListQueryOptions,
  developerOptionsQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type { DeveloperPublic } from '@/api/schemas'
import { formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

import { DeveloperRegistryImportPanel } from './DeveloperRegistryImportPanel'

const orderingOptions = [
  { value: 'name', label: 'По названию: А–Я' },
  { value: '-name', label: 'По названию: Я–А' },
  { value: 'companyGroup', label: 'По группе компаний' },
  { value: '-createdAt', label: 'Сначала новые' },
]

export function DeveloperListPage() {
  useDocumentTitle('Застройщики')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const sessionQuery = useQuery(sessionQueryOptions)
  const developerQuery = useQuery(developerListQueryOptions(searchParameters))
  const optionsQuery = useQuery(developerOptionsQueryOptions)
  const queryClient = useQueryClient()
  const [selectedDeveloper, setSelectedDeveloper] = (
    useState<DeveloperPublic | null>(null)
  )
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: (developerIdentifier: number) => (
      deleteDeveloper(developerIdentifier)
    ),
    onSuccess: async () => {
      setSelectedDeveloper(null)
      await queryClient.invalidateQueries({ queryKey: ['developers'] })
      window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
    },
  })

  useEffect(() => {
    if (!selectedDeveloper) return
    cancelButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleteMutation.isPending) {
        setSelectedDeveloper(null)
        window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [deleteMutation.isPending, selectedDeveloper])

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
    const searchInput = event.currentTarget.elements.namedItem('q')
    const searchValue = searchInput instanceof HTMLInputElement
      ? searchInput.value.trim()
      : ''
    updateParameters({ q: searchValue || null, page: null })
  }

  const openDeleteDialog = (
    developer: DeveloperPublic,
    trigger: HTMLButtonElement,
  ) => {
    deleteMutation.reset()
    deleteTriggerRef.current = trigger
    setSelectedDeveloper(developer)
  }

  const closeDeleteDialog = () => {
    if (deleteMutation.isPending) return
    setSelectedDeveloper(null)
    window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
  }

  if (developerQuery.isLoading) return <PageLoadingState />
  if (developerQuery.isError || !developerQuery.data) {
    return <ErrorState onRetry={() => void developerQuery.refetch()} />
  }

  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  const canSyncExternalData = (
    sessionQuery.data?.capabilities.syncExternalData === true
  )
  const { results, page, totalCount, totalPages } = developerQuery.data
  const companyGroups = optionsQuery.data?.companyGroups ?? []
  const regions = optionsQuery.data?.regions ?? []

  return (
    <div className="page-stack developer-list-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Недвижимость</span>
          <h1>Застройщики</h1>
          <p>
            Компании-застройщики, их корпоративные группы, регионы работы и
            связанные жилые комплексы.
          </p>
        </div>
        <div className="page-header__actions">
          <a className="button button--secondary" href="/property/developers/">
            Прежняя версия
          </a>
          {canManageCatalogs ? (
            <Link className="button button--primary" to="/developers/new">
              Добавить застройщика
            </Link>
          ) : null}
        </div>
      </header>

      {canSyncExternalData ? <DeveloperRegistryImportPanel /> : null}

      <section
        className="filter-panel developer-filter-panel"
        aria-label="Фильтры застройщиков"
      >
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <label htmlFor="developer-search">Поиск</label>
          <div className="search-control">
            <span aria-hidden="true">⌕</span>
            <input
              id="developer-search"
              name="q"
              type="search"
              key={searchParameters.get('q') ?? ''}
              defaultValue={searchParameters.get('q') ?? ''}
              placeholder="Название или группа компаний"
            />
            <button className="button button--dark" type="submit">
              Найти
            </button>
          </div>
        </form>
        <div className="sort-control">
          <label htmlFor="developer-company-group">Группа компаний</label>
          <select
            id="developer-company-group"
            value={searchParameters.get('companyGroupId') ?? ''}
            onChange={(event) => updateParameters({
              companyGroupId: event.target.value || null,
              page: null,
            })}
          >
            <option value="">Все группы</option>
            {companyGroups.map((companyGroup) => (
              <option value={companyGroup.id} key={companyGroup.id}>
                {companyGroup.name}
              </option>
            ))}
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="developer-region">Регион</label>
          <select
            id="developer-region"
            value={searchParameters.get('regionId') ?? ''}
            onChange={(event) => updateParameters({
              regionId: event.target.value || null,
              page: null,
            })}
          >
            <option value="">Все регионы</option>
            {regions.map((region) => (
              <option value={region.id} key={region.id}>{region.name}</option>
            ))}
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="developer-status">Статус</label>
          <select
            id="developer-status"
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
          <label htmlFor="developer-ordering">Сортировка</label>
          <select
            id="developer-ordering"
            value={searchParameters.get('ordering') ?? 'name'}
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
        {optionsQuery.data?.truncated.companyGroups
          || optionsQuery.data?.truncated.regions ? (
            <p className="filter-panel__notice" role="status">
              Показана только первая часть справочников. Полный перечень
              доступен в прежней версии.
            </p>
          ) : null}
      </section>

      <div className="results-heading" aria-live="polite">
        <p>Застройщиков: <strong>{formatInteger(totalCount)}</strong></p>
        {developerQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>

      {results.length === 0 ? (
        <EmptyState
          title="Застройщики не найдены"
          description="Измените параметры поиска или добавьте новую запись."
          action={canManageCatalogs ? (
            <Link className="button button--primary" to="/developers/new">
              Добавить застройщика
            </Link>
          ) : undefined}
        />
      ) : (
        <>
          <div className="table-card property-table-wrapper">
            <table className="property-table catalog-table developer-table">
              <caption className="visually-hidden">Список застройщиков</caption>
              <thead>
                <tr>
                  <th scope="col">Застройщик</th>
                  <th scope="col">Группа</th>
                  <th scope="col">Регионы</th>
                  <th scope="col">ЖК</th>
                  <th scope="col">Статус</th>
                  {canManageCatalogs ? (
                    <th scope="col">
                      <span className="visually-hidden">Действия</span>
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {results.map((developer) => (
                  <tr key={developer.id}>
                    <td><strong>{developer.name}</strong></td>
                    <td>{developer.companyGroup?.name ?? 'Без группы'}</td>
                    <td>
                      {developer.regions.length
                        ? developer.regions.map((region) => region.name).join(', ')
                        : 'Не указаны'}
                    </td>
                    <td>{formatInteger(developer.complexCount)}</td>
                    <td>
                      <span
                        className={developer.isActive
                          ? 'catalog-status'
                          : 'catalog-status catalog-status--inactive'}
                      >
                        {developer.isActive ? 'Активен' : 'Неактивен'}
                      </span>
                    </td>
                    {canManageCatalogs ? (
                      <td>
                        <div className="row-actions">
                          <Link
                            className="row-action"
                            to={`/developers/${developer.id}/edit`}
                            aria-label={`Редактировать: ${developer.name}`}
                          >
                            ✎
                          </Link>
                          <button
                            className="row-action row-action--danger"
                            type="button"
                            aria-label={`Удалить: ${developer.name}`}
                            onClick={(event) => openDeleteDialog(
                              developer,
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
            {results.map((developer) => (
              <article
                className="property-mobile-card catalog-mobile-card"
                key={developer.id}
              >
                <div className="property-mobile-card__heading">
                  <div>
                    <span>{developer.companyGroup?.name ?? 'Без группы'}</span>
                    <h2>{developer.name}</h2>
                  </div>
                  <span
                    className={developer.isActive
                      ? 'catalog-status'
                      : 'catalog-status catalog-status--inactive'}
                  >
                    {developer.isActive ? 'Активен' : 'Неактивен'}
                  </span>
                </div>
                <dl>
                  <div>
                    <dt>Регионы</dt>
                    <dd>
                      {developer.regions.length
                        ? developer.regions.map((region) => region.name).join(', ')
                        : 'Не указаны'}
                    </dd>
                  </div>
                  <div>
                    <dt>Жилых комплексов</dt>
                    <dd>{formatInteger(developer.complexCount)}</dd>
                  </div>
                </dl>
                {canManageCatalogs ? (
                  <div className="property-mobile-card__actions">
                    <Link
                      className="text-link"
                      to={`/developers/${developer.id}/edit`}
                    >
                      Редактировать
                    </Link>
                    <button
                      className="text-button text-button--danger"
                      type="button"
                      onClick={(event) => openDeleteDialog(
                        developer,
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
        <nav className="pagination" aria-label="Страницы застройщиков">
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

      {selectedDeveloper ? (
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
            aria-labelledby="developer-delete-title"
            aria-describedby="developer-delete-description"
          >
            <span className="eyebrow">Подтверждение</span>
            <h2 id="developer-delete-title">Удалить застройщика?</h2>
            <p id="developer-delete-description">
              «{selectedDeveloper.name}» будет удалён без возможности
              восстановления.
            </p>
            {deleteMutation.isError ? (
              <p className="form-error" role="alert">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'Сначала удалите или переназначьте связанные ЖК.'
                  : 'Не удалось удалить застройщика. Повторите попытку.'}
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
                onClick={() => deleteMutation.mutate(selectedDeveloper.id)}
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
