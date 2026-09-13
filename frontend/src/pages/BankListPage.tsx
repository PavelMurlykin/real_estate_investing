import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  bankListQueryOptions,
  deleteBank,
  sessionQueryOptions,
} from '@/api/queries'
import type { BankListItem } from '@/api/schemas'
import { formatInteger, formatPercent } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

const orderingOptions = [
  { value: 'name', label: 'По названию: А–Я' },
  { value: '-name', label: 'По названию: Я–А' },
  { value: 'minimumInterestRate', label: 'Сначала с низкой ставкой' },
  { value: '-minimumInterestRate', label: 'Сначала с высокой ставкой' },
  { value: '-updatedAt', label: 'Недавно изменённые' },
]

function BankIdentity({ bank }: { bank: BankListItem }) {
  return (
    <div className="bank-identity">
      <span className="bank-logo" aria-hidden="true">
        {bank.logoUrl ? (
          <img
            src={bank.logoUrl}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : bank.name.slice(0, 1).toUpperCase()}
      </span>
      <Link className="text-link" to={`/banks/${bank.id}`}>
        {bank.name}
      </Link>
    </div>
  )
}

export function BankListPage() {
  useDocumentTitle('Банки и программы')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const bankQuery = useQuery(bankListQueryOptions(searchParameters))
  const sessionQuery = useQuery(sessionQueryOptions)
  const queryClient = useQueryClient()
  const [selectedBank, setSelectedBank] = useState<BankListItem | null>(null)
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: (bankIdentifier: number) => deleteBank(bankIdentifier),
    onSuccess: async () => {
      setSelectedBank(null)
      await queryClient.invalidateQueries({ queryKey: ['banks'] })
      window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
    },
  })

  useEffect(() => {
    if (!selectedBank) return
    cancelButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleteMutation.isPending) {
        setSelectedBank(null)
        window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [deleteMutation.isPending, selectedBank])

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
    bank: BankListItem,
    trigger: HTMLButtonElement,
  ) => {
    deleteMutation.reset()
    deleteTriggerRef.current = trigger
    setSelectedBank(bank)
  }

  const closeDeleteDialog = () => {
    if (deleteMutation.isPending) return
    setSelectedBank(null)
    window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
  }

  if (bankQuery.isLoading) return <PageLoadingState />
  if (bankQuery.isError || !bankQuery.data) {
    return <ErrorState onRetry={() => void bankQuery.refetch()} />
  }

  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  const { results, page, totalCount, totalPages } = bankQuery.data

  return (
    <div className="page-stack bank-list-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Финансовые справочники</span>
          <h1>Банки и программы</h1>
          <p>
            Банки, доступные ипотечные программы, ставки, первый взнос и
            предельный срок кредита.
          </p>
        </div>
        <div className="page-header__actions">
          <a className="button button--secondary" href="/bank/">
            Прежняя версия
          </a>
          {canManageCatalogs ? (
            <Link className="button button--primary" to="/banks/new">
              Добавить банк
            </Link>
          ) : null}
        </div>
      </header>

      <nav className="dictionary-tabs" aria-label="Разделы банков">
        <Link to="/banks" aria-current="page">Банки</Link>
        <Link to="/mortgage-programs">Ипотечные программы</Link>
        <Link to="/developer-programs">
          Программы застройщиков
        </Link>
        <Link to="/key-rate">Ключевая ставка</Link>
      </nav>

      <section
        className="filter-panel bank-filter-panel"
        aria-label="Фильтры банков"
      >
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <label htmlFor="bank-search">Поиск</label>
          <div className="search-control">
            <span aria-hidden="true">⌕</span>
            <input
              id="bank-search"
              name="q"
              type="search"
              key={searchParameters.get('q') ?? ''}
              defaultValue={searchParameters.get('q') ?? ''}
              placeholder="Название банка"
            />
            <button className="button button--dark" type="submit">
              Найти
            </button>
          </div>
        </form>
        <div className="sort-control">
          <label htmlFor="bank-program-scope">Программы</label>
          <select
            id="bank-program-scope"
            value={searchParameters.get('scope') ?? 'all'}
            onChange={(event) => updateParameters({
              scope: event.target.value,
              page: null,
            })}
          >
            <option value="all">Все банки</option>
            <option value="withPrograms">С программами</option>
            <option value="withoutPrograms">Без программ</option>
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="bank-status">Статус</label>
          <select
            id="bank-status"
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
          <label htmlFor="bank-ordering">Сортировка</label>
          <select
            id="bank-ordering"
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
        <p>Банков: <strong>{formatInteger(totalCount)}</strong></p>
        {bankQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>

      {results.length === 0 ? (
        <EmptyState
          title="Банки не найдены"
          description="Измените параметры поиска или добавьте новую запись."
          action={canManageCatalogs ? (
            <Link className="button button--primary" to="/banks/new">
              Добавить банк
            </Link>
          ) : undefined}
        />
      ) : (
        <>
          <div className="table-card property-table-wrapper">
            <table className="property-table catalog-table bank-table">
              <caption className="visually-hidden">Список банков</caption>
              <thead>
                <tr>
                  <th scope="col">Банк</th>
                  <th scope="col">Программ</th>
                  <th scope="col">Мин. ставка</th>
                  <th scope="col">Статус</th>
                  {canManageCatalogs ? (
                    <th scope="col"><span className="visually-hidden">Действия</span></th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {results.map((bank) => (
                  <tr key={bank.id}>
                    <td><BankIdentity bank={bank} /></td>
                    <td>{formatInteger(bank.programCount)}</td>
                    <td>
                      {bank.minimumInterestRate
                        ? `от ${formatPercent(bank.minimumInterestRate)}`
                        : '—'}
                    </td>
                    <td>
                      <span className={bank.isActive
                        ? 'catalog-status'
                        : 'catalog-status catalog-status--inactive'}>
                        {bank.isActive ? 'Активен' : 'Неактивен'}
                      </span>
                    </td>
                    {canManageCatalogs ? (
                      <td>
                        <div className="row-actions">
                          <Link
                            className="row-action"
                            to={`/banks/${bank.id}/edit`}
                            aria-label={`Редактировать: ${bank.name}`}
                          >
                            ✎
                          </Link>
                          <button
                            className="row-action row-action--danger"
                            type="button"
                            aria-label={`Удалить: ${bank.name}`}
                            onClick={(event) => openDeleteDialog(
                              bank,
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
            {results.map((bank) => (
              <article
                className="property-mobile-card catalog-mobile-card"
                key={bank.id}
              >
                <div className="property-mobile-card__heading">
                  <div>
                    <span>Банк</span>
                    <h2><Link className="text-link" to={`/banks/${bank.id}`}>{bank.name}</Link></h2>
                  </div>
                  <span className={bank.isActive
                    ? 'catalog-status'
                    : 'catalog-status catalog-status--inactive'}>
                    {bank.isActive ? 'Активен' : 'Неактивен'}
                  </span>
                </div>
                <dl>
                  <div><dt>Программ</dt><dd>{formatInteger(bank.programCount)}</dd></div>
                  <div>
                    <dt>Мин. ставка</dt>
                    <dd>{bank.minimumInterestRate
                      ? formatPercent(bank.minimumInterestRate)
                      : '—'}</dd>
                  </div>
                </dl>
                <div className="property-mobile-card__actions">
                  <Link className="text-link" to={`/banks/${bank.id}`}>
                    Открыть
                  </Link>
                  {canManageCatalogs ? (
                    <>
                      <Link className="text-link" to={`/banks/${bank.id}/edit`}>
                        Редактировать
                      </Link>
                      <button
                        className="text-button text-button--danger"
                        type="button"
                        onClick={(event) => openDeleteDialog(
                          bank,
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
        <nav className="pagination" aria-label="Страницы банков">
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

      {selectedBank ? (
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
            aria-labelledby="bank-delete-title"
            aria-describedby="bank-delete-description"
          >
            <span className="eyebrow">Подтверждение</span>
            <h2 id="bank-delete-title">Удалить банк?</h2>
            <p id="bank-delete-description">
              «{selectedBank.name}» и его банковские условия будут удалены.
            </p>
            {deleteMutation.isError ? (
              <p className="form-error" role="alert">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'Банк используется в программах застройщиков. Сначала переназначьте эти связи.'
                  : 'Не удалось удалить банк. Повторите попытку.'}
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
                onClick={() => deleteMutation.mutate(selectedBank.id)}
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
