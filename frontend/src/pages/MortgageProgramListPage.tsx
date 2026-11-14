import { BankCatalogNavigation } from '@/features/bank/BankCatalogNavigation'
import { Notice } from '@/shared/ui/Notice'
import { restoreFocus } from '@/shared/lib/restoreFocus'
import { ModalDialog } from '@/shared/ui/ModalDialog'
import { SelectFilter } from '@/shared/ui/SelectFilter'
import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { Pagination } from '@/shared/ui/Pagination'
import { BankCatalogImport } from '@/shared/ui/BankCatalogImport'
import { ResetFilters } from '@/shared/ui/ResetFilters'
import { useTableParameters } from '@/shared/lib/useTableParameters'
import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { SortableHeader } from '@/shared/ui/SortableHeader'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
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

export function MortgageProgramListPage() {
  useDocumentTitle('Ипотечные программы')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const tableParameters = useTableParameters(searchParameters)
  const programQuery = useQuery(
    mortgageProgramListQueryOptions(tableParameters),
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
      window.setTimeout(() => restoreFocus(deleteTriggerRef.current), 0)
    },
  })

  const updateParameters = (updates: Record<string, string | null>) => {
    const nextParameters = new URLSearchParams(searchParameters)
    Object.entries(updates).forEach(([fieldName, value]) => {
      if (!value || value === 'all') nextParameters.delete(fieldName)
      else nextParameters.set(fieldName, value)
    })
    setSearchParameters(nextParameters)
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
    window.setTimeout(() => restoreFocus(deleteTriggerRef.current), 0)
  }

  if (programQuery.isLoading) return <PageLoadingState />
  if (programQuery.isError || !programQuery.data) {
    return <ErrorState onRetry={() => programQuery.refetch()} />
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
          <p>Справочник ипотечных программ, их условий и кредитных лимитов.</p>
        </div>
        {canManageCatalogs ? (
          <div className="page-header__actions">
            <Link
              className="button button--primary"
              to="/mortgage-programs/new"
            >
              Добавить программу
            </Link>
          </div>
        ) : null}
      </header>

      <BankCatalogNavigation />

      {sessionQuery.data?.capabilities.syncExternalData ? <BankCatalogImport section="mortgage-programs" /> : null}

      <section
        className="filter-panel mortgage-program-filter-panel"
        aria-label="Фильтры ипотечных программ"
      >
        <SelectFilter label="Тип программы" parameter="programType" emptyLabel="Все программы"
          options={[{ value: 'preferential', label: 'Льготные' }, { value: 'market', label: 'Рыночные' }]} />
        <div className="live-search-control" role="search">
          <LiveFilterInput label="Поиск" id="mortgage-program-search" parameter="q" placeholder="Название или описание" />
          <ResetFilters />
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
        <TableScrollArea className="table-card property-table-wrapper" label="Список ипотечных программ">
          <table className="property-table mortgage-program-table">
            <caption className="visually-hidden">
              Список ипотечных программ
            </caption>
            <colgroup>
              <col className="mortgage-program-table__name" />
              <col />
              <col className="mortgage-program-table__type" />
              <col className="mortgage-program-table__limit" />
              {canManageCatalogs ? <col className="mortgage-program-table__actions" /> : null}
            </colgroup>
            <thead>
              <tr>
                <SortableHeader field="name" defaultOrdering="name">Программа</SortableHeader>
                <th scope="col">Описание</th>
                <SortableHeader field="isPreferential" defaultOrdering="name">Тип</SortableHeader>
                <SortableHeader field="creditLimit" defaultOrdering="name">Кредитный лимит</SortableHeader>
                {canManageCatalogs ? (
                  <th scope="col"><span className="visually-hidden">Действия</span></th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {results.map((mortgageProgram) => (
                <tr key={mortgageProgram.id}>
                  <td>
                    <Link
                      className="text-link"
                      to={`/mortgage-programs/${mortgageProgram.id}`}
                    >
                      {mortgageProgram.name}
                    </Link>
                  </td>
                  <td className="mortgage-program-description">{mortgageProgram.condition || '—'}</td>
                  <td>
                    {mortgageProgram.isPreferential ? 'Льготная' : 'Рыночная'}
                  </td>
                  <td>
                    {mortgageProgram.creditLimit
                      ? formatCurrency(mortgageProgram.creditLimit)
                      : '—'}
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
        </TableScrollArea>
      )}

      {totalPages > 1 ? (
        <Pagination label="Страницы ипотечных программ" page={page} totalPages={totalPages} onPageChange={(nextPage) => updateParameters({ page: String(nextPage) })} />
      ) : null}

      {selectedProgram ? (
        <ModalDialog labelledBy="mortgage-program-delete-title" describedBy="mortgage-program-delete-description" pending={deleteMutation.isPending} onClose={closeDeleteDialog}>
            <span className="eyebrow">Подтверждение</span>
            <h2 id="mortgage-program-delete-title">Удалить программу?</h2>
            <p id="mortgage-program-delete-description">
              «{selectedProgram.name}», её лимиты будут удалены.
            </p>
            {deleteMutation.isError ? (
              <Notice as="p" tone="error" role="alert" className="form-error">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'Программа используется банком или программой застройщика. Сначала переназначьте эти связи.'
                  : 'Не удалось удалить программу. Повторите попытку.'}
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
                onClick={() => deleteMutation.mutate(selectedProgram.id)}
              >
                {deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}
              </button>
            </div>
          </ModalDialog>
      ) : null}
    </div>
  )
}
