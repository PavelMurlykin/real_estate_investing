import { Notice } from '@/shared/ui/Notice'
import { restoreFocus } from '@/shared/lib/restoreFocus'
import { ModalDialog } from '@/shared/ui/ModalDialog'
import { SelectFilter } from '@/shared/ui/SelectFilter'
import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { Pagination } from '@/shared/ui/Pagination'
import { ResetFilters } from '@/shared/ui/ResetFilters'
import { useTableParameters } from '@/shared/lib/useTableParameters'
import { useTableSearchParams } from '@/shared/lib/useTableSearchParams'
import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { SortableHeader } from '@/shared/ui/SortableHeader'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { BankCatalogImport } from '@/shared/ui/BankCatalogImport'
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

function BankProgramDisclosure({ bank }: { bank: BankListItem }) {
  if (bank.programs.length === 0) return null

  return (
    <details className="bank-program-disclosure">
      <summary aria-label={'Ипотечные программы — ' + bank.name}>Ипотечные программы</summary>
      <ul>
        {bank.programs.map((program) => (
          <li key={program.id}>
            <Link className="text-link" to={'/mortgage-programs/' + program.mortgageProgramId}>
              {program.mortgageProgramName}
            </Link>
            <span>
              от {formatPercent(program.interestRate)} · взнос от {formatPercent(program.minimumInitialPaymentPercent)}
              {program.maximumLoanTermYears ? ' · до ' + program.maximumLoanTermYears + ' лет' : ''}
            </span>
          </li>
        ))}
      </ul>
    </details>
  )
}

export function BankListPage() {
  useDocumentTitle('Банки и программы')
  const [searchParameters, updateSearchParameters] = useTableSearchParams()
  const tableParameters = useTableParameters(searchParameters)
  const bankQuery = useQuery(bankListQueryOptions(tableParameters))
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
      window.setTimeout(() => restoreFocus(deleteTriggerRef.current), 0)
    },
  })

  const updateParameters = (updates: Record<string, string | null>) => {
    updateSearchParameters((nextParameters) => {
      for (const [fieldName, value] of Object.entries(updates)) {
        if (!value || value === 'all') nextParameters.delete(fieldName)
        else nextParameters.set(fieldName, value)
      }
    })
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
    window.setTimeout(() => restoreFocus(deleteTriggerRef.current), 0)
  }

  if (bankQuery.isLoading) return <PageLoadingState />
  if (bankQuery.isError || !bankQuery.data) {
    return <ErrorState onRetry={() => bankQuery.refetch()} />
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
        {canManageCatalogs ? (
          <Link className="button button--primary" to="/banks/new">Добавить банк</Link>
        ) : null}
      </header>

      <nav className="dictionary-tabs" aria-label="Разделы банков">
        <Link to="/banks" aria-current="page">Банки</Link>
        <Link to="/mortgage-programs">Ипотечные программы</Link>
        <Link to="/developer-programs">
          Программы застройщиков
        </Link>
        <Link to="/key-rate">Ключевая ставка</Link>
      </nav>

      {sessionQuery.data?.capabilities.syncExternalData ? <BankCatalogImport section="banks" /> : null}

      <section
        className="filter-panel bank-filter-panel"
        aria-label="Фильтры банков"
      >
        <div role="search">
          <LiveFilterInput label="Поиск" id="bank-search" parameter="q" placeholder="Название банка" />
        </div>
        <div className="live-search-control">
          <SelectFilter label="Программы" parameter="scope" emptyLabel="Все банки"
          options={[{ value: 'withPrograms', label: 'С программами' }, { value: 'withoutPrograms', label: 'Без программ' }]} />
          <ResetFilters />
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
          <TableScrollArea className="table-card property-table-wrapper" label="Список банков">
            <table className="property-table bank-table">
              <caption className="visually-hidden">Список банков</caption>
              <colgroup>
                <col />
                <col className="bank-table__numeric" />
                <col className="bank-table__numeric" />
                {canManageCatalogs ? <col className="bank-table__actions" /> : null}
              </colgroup>
              <thead>
                <tr>
                  <SortableHeader field="name" defaultOrdering="name">Банк</SortableHeader>
                  <SortableHeader field="programCount" defaultOrdering="name">Программ</SortableHeader>
                  <SortableHeader field="minimumInterestRate" defaultOrdering="name">Мин. ставка</SortableHeader>

                  {canManageCatalogs ? (
                    <th scope="col"><span className="visually-hidden">Действия</span></th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {results.map((bank) => (
                  <tr key={bank.id}>
                    <td>
                      <BankIdentity bank={bank} />
                      <BankProgramDisclosure bank={bank} />
                    </td>
                    <td>{formatInteger(bank.programCount)}</td>
                    <td>
                      {bank.minimumInterestRate
                        ? `от ${formatPercent(bank.minimumInterestRate)}`
                        : '—'}
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
          </TableScrollArea>
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
                <BankProgramDisclosure bank={bank} />
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
        <Pagination label="Страницы банков" page={page} totalPages={totalPages} onPageChange={(nextPage) => updateParameters({ page: String(nextPage) })} />
      ) : null}

      {selectedBank ? (
        <ModalDialog labelledBy="bank-delete-title" describedBy="bank-delete-description" pending={deleteMutation.isPending} onClose={closeDeleteDialog}>
            <span className="eyebrow">Подтверждение</span>
            <h2 id="bank-delete-title">Удалить банк?</h2>
            <p id="bank-delete-description">
              «{selectedBank.name}» и его банковские условия будут удалены.
            </p>
            {deleteMutation.isError ? (
              <Notice as="p" tone="error" role="alert" className="form-error">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'Банк используется в программах застройщиков. Сначала переназначьте эти связи.'
                  : 'Не удалось удалить банк. Повторите попытку.'}
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
                onClick={() => deleteMutation.mutate(selectedBank.id)}
              >
                {deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}
              </button>
            </div>
          </ModalDialog>
      ) : null}
    </div>
  )
}
