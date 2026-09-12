import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  deleteMortgageProgram,
  mortgageProgramListQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type { MortgageProgramListItem } from '@/api/schemas'
import { formatCurrency, formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

const orderingOptions = [
  { value: 'name', label: 'По названию: А–Я' },
  { value: '-name', label: 'По названию: Я–А' },
  { value: 'creditLimit', label: 'Сначала с меньшим лимитом' },
  { value: '-creditLimit', label: 'Сначала с большим лимитом' },
  { value: '-updatedAt', label: 'Недавно изменённые' },
]

function usageLabel(mortgageProgram: MortgageProgramListItem) {
  const usageCount = (
    mortgageProgram.bankCount + mortgageProgram.developerProgramCount
  )
  return usageCount
    ? `${formatInteger(usageCount)} связей`
    : 'Не используется'
}

export function MortgageProgramListPage() {
  useDocumentTitle('Ипотечные программы')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const programQuery = useQuery(
    mortgageProgramListQueryOptions(searchParameters),
  )
  const sessionQuery = useQuery(sessionQueryOptions)
  const queryClient = useQueryClient()
  const [selectedProgram, setSelectedProgram] = (
    useState<MortgageProgramListItem | null>(null)
  )
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: (mortgageProgramIdentifier: number) => (
      deleteMortgageProgram(mortgageProgramIdentifier)
    ),
    onSuccess: async () => {
      setSelectedProgram(null)
      await queryClient.invalidateQueries({ queryKey: ['mortgage-programs'] })
      window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
    },
  })

  useEffect(() => {
    if (!selectedProgram) return
    cancelButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleteMutation.isPending) {
        setSelectedProgram(null)
        window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [deleteMutation.isPending, selectedProgram])

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
    mortgageProgram: MortgageProgramListItem,
    trigger: HTMLButtonElement,
  ) => {
    deleteMutation.reset()
    deleteTriggerRef.current = trigger
    setSelectedProgram(mortgageProgram)
  }

  const closeDeleteDialog = () => {
    if (deleteMutation.isPending) return
    setSelectedProgram(null)
    window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
  }

  if (programQuery.isLoading) return <PageLoadingState />
  if (programQuery.isError || !programQuery.data) {
    return <ErrorState onRetry={() => void programQuery.refetch()} />
  }

  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  const { results, page, totalCount, totalPages } = programQuery.data

  return (
    <div className="page-stack mortgage-program-list-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Финансовые справочники</span>
          <h1>Ипотечные программы</h1>
          <p>
            Единые названия программ, федеральные и региональные лимиты,
            а также алиасы для сопоставления импортируемых данных.
          </p>
        </div>
        <div className="page-header__actions">
          <a
            className="button button--secondary"
            href="/bank/?model=mortgage_program"
          >
            Прежняя версия
          </a>
          {canManageCatalogs ? (
            <Link
              className="button button--primary"
              to="/mortgage-programs/new"
            >
              Добавить программу
            </Link>
          ) : null}
        </div>
      </header>

      <nav className="dictionary-tabs" aria-label="Разделы банков">
        <Link to="/banks">Банки</Link>
        <Link to="/mortgage-programs" aria-current="page">
          Ипотечные программы
        </Link>
        <a href="/bank/developer-programs/">Программы застройщиков</a>
      </nav>

      <section
        className="filter-panel mortgage-program-filter-panel"
        aria-label="Фильтры ипотечных программ"
      >
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <label htmlFor="mortgage-program-search">Поиск</label>
          <div className="search-control">
            <span aria-hidden="true">⌕</span>
            <input
              id="mortgage-program-search"
              name="q"
              type="search"
              key={searchParameters.get('q') ?? ''}
              defaultValue={searchParameters.get('q') ?? ''}
              placeholder="Название, условие или алиас"
            />
            <button className="button button--dark" type="submit">
              Найти
            </button>
          </div>
        </form>
        <div className="sort-control">
          <label htmlFor="mortgage-program-type">Тип программы</label>
          <select
            id="mortgage-program-type"
            value={searchParameters.get('programType') ?? 'all'}
            onChange={(event) => updateParameters({
              programType: event.target.value,
              page: null,
            })}
          >
            <option value="all">Все программы</option>
            <option value="preferential">Льготные</option>
            <option value="market">Рыночные</option>
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="mortgage-program-status">Статус</label>
          <select
            id="mortgage-program-status"
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
          <label htmlFor="mortgage-program-ordering">Сортировка</label>
          <select
            id="mortgage-program-ordering"
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
      </section>

      <div className="results-heading" aria-live="polite">
        <p>Программ: <strong>{formatInteger(totalCount)}</strong></p>
        {programQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>

      {results.length === 0 ? (
        <EmptyState
          title="Ипотечные программы не найдены"
          description="Измените фильтры или добавьте новую программу."
          action={canManageCatalogs ? (
            <Link
              className="button button--primary"
              to="/mortgage-programs/new"
            >
              Добавить программу
            </Link>
          ) : undefined}
        />
      ) : (
        <>
          <div className="table-card property-table-wrapper">
            <table className="property-table catalog-table mortgage-program-table">
              <caption className="visually-hidden">
                Список ипотечных программ
              </caption>
              <thead>
                <tr>
                  <th scope="col">Программа</th>
                  <th scope="col">Тип</th>
                  <th scope="col">Кредитный лимит</th>
                  <th scope="col">Использование</th>
                  <th scope="col">Лимиты / алиасы</th>
                  <th scope="col">Статус</th>
                  {canManageCatalogs ? (
                    <th scope="col"><span className="visually-hidden">Действия</span></th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {results.map((mortgageProgram) => (
                  <tr key={mortgageProgram.id}>
                    <td className="mortgage-program-name-cell">
                      <Link
                        className="text-link"
                        to={`/mortgage-programs/${mortgageProgram.id}`}
                      >
                        {mortgageProgram.name}
                      </Link>
                      <small>{mortgageProgram.condition}</small>
                    </td>
                    <td>
                      {mortgageProgram.isPreferential ? 'Льготная' : 'Рыночная'}
                    </td>
                    <td>
                      {mortgageProgram.creditLimit
                        ? formatCurrency(mortgageProgram.creditLimit)
                        : '—'}
                    </td>
                    <td>{usageLabel(mortgageProgram)}</td>
                    <td>
                      {formatInteger(mortgageProgram.regionalLimitCount)} /{' '}
                      {formatInteger(mortgageProgram.aliasCount)}
                    </td>
                    <td>
                      <span className={mortgageProgram.isActive
                        ? 'catalog-status'
                        : 'catalog-status catalog-status--inactive'}>
                        {mortgageProgram.isActive ? 'Активна' : 'Неактивна'}
                      </span>
                    </td>
                    {canManageCatalogs ? (
                      <td>
                        <div className="row-actions">
                          <Link
                            className="row-action"
                            to={`/mortgage-programs/${mortgageProgram.id}/edit`}
                            aria-label={`Редактировать: ${mortgageProgram.name}`}
                          >
                            ✎
                          </Link>
                          <button
                            className="row-action row-action--danger"
                            type="button"
                            aria-label={`Удалить: ${mortgageProgram.name}`}
                            onClick={(event) => openDeleteDialog(
                              mortgageProgram,
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
            {results.map((mortgageProgram) => (
              <article className="property-mobile-card" key={mortgageProgram.id}>
                <div className="property-mobile-card__heading">
                  <div>
                    <span>
                      {mortgageProgram.isPreferential ? 'Льготная' : 'Рыночная'}
                    </span>
                    <h2>
                      <Link
                        className="text-link"
                        to={`/mortgage-programs/${mortgageProgram.id}`}
                      >
                        {mortgageProgram.name}
                      </Link>
                    </h2>
                  </div>
                  <span className={mortgageProgram.isActive
                    ? 'catalog-status'
                    : 'catalog-status catalog-status--inactive'}>
                    {mortgageProgram.isActive ? 'Активна' : 'Неактивна'}
                  </span>
                </div>
                <p className="mortgage-program-mobile-condition">
                  {mortgageProgram.condition}
                </p>
                <dl>
                  <div>
                    <dt>Кредитный лимит</dt>
                    <dd>{mortgageProgram.creditLimit
                      ? formatCurrency(mortgageProgram.creditLimit)
                      : '—'}</dd>
                  </div>
                  <div><dt>Использование</dt><dd>{usageLabel(mortgageProgram)}</dd></div>
                  <div>
                    <dt>Региональных лимитов</dt>
                    <dd>{formatInteger(mortgageProgram.regionalLimitCount)}</dd>
                  </div>
                  <div><dt>Алиасов</dt><dd>{formatInteger(mortgageProgram.aliasCount)}</dd></div>
                </dl>
                <div className="property-mobile-card__actions">
                  <Link
                    className="text-link"
                    to={`/mortgage-programs/${mortgageProgram.id}`}
                  >
                    Открыть
                  </Link>
                  {canManageCatalogs ? (
                    <>
                      <Link
                        className="text-link"
                        to={`/mortgage-programs/${mortgageProgram.id}/edit`}
                      >
                        Редактировать
                      </Link>
                      <button
                        className="text-button text-button--danger"
                        type="button"
                        onClick={(event) => openDeleteDialog(
                          mortgageProgram,
                          event.currentTarget,
                        )}
                      >
                        Удалить
                      </button>
                    </>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </>
      )}

      {totalPages > 1 ? (
        <nav className="pagination" aria-label="Страницы ипотечных программ">
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

      {selectedProgram ? (
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
            aria-labelledby="mortgage-program-delete-title"
            aria-describedby="mortgage-program-delete-description"
          >
            <span className="eyebrow">Подтверждение</span>
            <h2 id="mortgage-program-delete-title">Удалить программу?</h2>
            <p id="mortgage-program-delete-description">
              «{selectedProgram.name}», её лимиты и алиасы будут удалены.
            </p>
            {deleteMutation.isError ? (
              <p className="form-error" role="alert">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'Программа используется банком или программой застройщика. Сначала переназначьте эти связи.'
                  : 'Не удалось удалить программу. Повторите попытку.'}
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
                onClick={() => deleteMutation.mutate(selectedProgram.id)}
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
