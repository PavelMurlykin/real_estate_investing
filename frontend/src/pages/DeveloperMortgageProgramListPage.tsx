import { BankCatalogNavigation } from '@/features/bank/BankCatalogNavigation'
import { retryFailedQueries } from '@/shared/lib/retryFailedQueries'
import { Notice } from '@/shared/ui/Notice'
import { restoreFocus } from '@/shared/lib/restoreFocus'
import { ModalDialog } from '@/shared/ui/ModalDialog'
import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { Pagination } from '@/shared/ui/Pagination'
import { ResetFilters } from '@/shared/ui/ResetFilters'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'
import { useTableParameters } from '@/shared/lib/useTableParameters'
import { useTableSearchParams } from '@/shared/lib/useTableSearchParams'
import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { SortableHeader } from '@/shared/ui/SortableHeader'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  deleteDeveloperMortgageProgram,
  developerMortgageProgramListQueryOptions,
  developerMortgageProgramOptionsQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type { DeveloperMortgageProgram } from '@/api/schemas'
import { formatCurrency, formatInteger, formatPercent } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

import { DeveloperMortgageProgramImportPanel } from './DeveloperMortgageProgramImportPanel'

function scopeName(program: DeveloperMortgageProgram) {
  return program.realEstateComplexName ?? 'Все ЖК группы'
}

function valueOrDash(value: string | null, formatter = formatPercent) {
  return value === null ? '—' : formatter(value)
}

export function DeveloperMortgageProgramListPage() {
  useDocumentTitle('Программы застройщиков')
  const [searchParameters, updateSearchParameters] = useTableSearchParams()
  const tableParameters = useTableParameters(searchParameters)
  const selectedCompanyGroup = Number(
    searchParameters.get('companyGroupId') ?? 0,
  ) || null
  const programQuery = useQuery(
    developerMortgageProgramListQueryOptions(tableParameters),
  )
  const optionsQuery = useQuery(
    developerMortgageProgramOptionsQueryOptions(selectedCompanyGroup),
  )
  const sessionQuery = useQuery(sessionQueryOptions)
  const queryClient = useQueryClient()
  const [selectedProgram, setSelectedProgram] = (
    useState<DeveloperMortgageProgram | null>(null)
  )
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: (identifier: number) => deleteDeveloperMortgageProgram(identifier),
    onSuccess: async () => {
      setSelectedProgram(null)
      await queryClient.invalidateQueries({
        queryKey: ['developer-mortgage-programs'],
      })
      window.setTimeout(() => restoreFocus(deleteTriggerRef.current), 0)
    },
  })

  const updateParameters = (updates: Record<string, string | null>) => {
    updateSearchParameters((nextParameters) => {
      const companyGroup = updates.companyGroupId
      if (companyGroup && companyGroup !== nextParameters.get('companyGroupId')) {
        nextParameters.delete('realEstateComplexId')
      }
      for (const [fieldName, value] of Object.entries(updates)) {
        if (value) nextParameters.set(fieldName, value)
        else nextParameters.delete(fieldName)
      }
    })
  }
  const canManage = sessionQuery.data?.capabilities.manageCatalogs === true

  if (programQuery.isLoading || optionsQuery.isLoading) {
    return <PageLoadingState />
  }
  if (programQuery.isError || !programQuery.data) {
    return <ErrorState onRetry={() => retryFailedQueries(programQuery, optionsQuery)} />
  }
  if (optionsQuery.isError || !optionsQuery.data) {
    return (
      <ErrorState
        title="Не удалось загрузить фильтры программ"
        onRetry={() => retryFailedQueries(optionsQuery, programQuery)}
      />
    )
  }

  const { results, page, totalCount, totalPages } = programQuery.data
  const options = optionsQuery.data
  return (
    <div className="page-stack developer-program-list-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Специальные условия</span>
          <h1>Программы застройщиков</h1>
          <p>
            Ипотечные условия групп компаний и отдельных жилых комплексов.
          </p>
        </div>
        {canManage ? (
          <div className="page-header__actions">
            <Link className="button button--primary" to="/developer-programs/new">
              Добавить программу
            </Link>
          </div>
        ) : null}
      </header>

      <BankCatalogNavigation />

      {canManage ? <DeveloperMortgageProgramImportPanel /> : null}

      <section
        className="filter-panel developer-program-filter-panel"
        aria-label="Фильтры программ застройщиков"
      >
        <div className="developer-program-filter-panel__search" role="search">
          <LiveFilterInput label="Поиск" id="developer-program-search" parameter="q" placeholder="Группа, ЖК, банк или программа" />
        </div>
        <RemoteSelect filter dictionary="company-groups" label="Группа компаний" value={searchParameters.get('companyGroupId') ?? ''}
            initialOptions={options.companyGroups.map((option) => ({ id: option.id, label: option.name }))}
            onChange={(value) => updateParameters({
              companyGroupId: value || null,
              page: null,
            })} />
        <RemoteSelect filter dictionary="complexes" label="Жилой комплекс" value={searchParameters.get('realEstateComplexId') ?? ''}
            initialOptions={options.realEstateComplexes.map((option) => ({ id: option.id, label: option.name }))}
            filters={{ companyGroupId: searchParameters.get('companyGroupId') }}
            onChange={(value) => updateParameters({
              realEstateComplexId: value || null,
              page: null,
            })} />
        <RemoteSelect filter dictionary="banks" label="Банк" value={searchParameters.get('bankId') ?? ''}
            initialOptions={options.banks.map((option) => ({ id: option.id, label: option.name }))}
            onChange={(value) => updateParameters({
              bankId: value || null,
              page: null,
            })} />
        <div className="live-search-control developer-program-filter-panel__last">
          <RemoteSelect filter dictionary="mortgage-programs" label="Программа" value={searchParameters.get('mortgageProgramId') ?? ''}
            initialOptions={options.mortgagePrograms.map((option) => ({ id: option.id, label: option.name }))}
            onChange={(value) => updateParameters({
              mortgageProgramId: value || null,
              page: null,
            })} />
          <ResetFilters />
        </div>
      </section>

      <div className="results-heading" aria-live="polite">
        <p>Программ: <strong>{formatInteger(totalCount)}</strong></p>
        {programQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>
      {results.length === 0 ? (
        <EmptyState
          title="Программы застройщиков не найдены"
          description="Измените фильтры или добавьте новую программу."
          action={canManage ? (
            <Link className="button button--primary" to="/developer-programs/new">
              Добавить программу
            </Link>
          ) : undefined}
        />
      ) : (
        <>
          <TableScrollArea className="table-card property-table-wrapper" label="Список программ застройщиков">
            <table className="property-table developer-program-table">
              <caption className="visually-hidden">
                Список программ застройщиков
              </caption>
              <thead>
                <tr>
                  <SortableHeader field="companyGroup" defaultOrdering="companyGroup">Группа и область</SortableHeader>
                  <SortableHeader field="bank" defaultOrdering="companyGroup">Банк и программа</SortableHeader>
                  <SortableHeader field="interestRate" defaultOrdering="companyGroup">Ставка</SortableHeader>
                  <SortableHeader field="gracePeriodMonths" defaultOrdering="companyGroup">Льготный период</SortableHeader>
                  <SortableHeader field="minimumInitialPaymentPercent" defaultOrdering="companyGroup">Первый взнос</SortableHeader>
                  <SortableHeader field="maximumLoanAmount" defaultOrdering="companyGroup">Лимит и срок</SortableHeader>
                  <SortableHeader field="priceIncreasePercent" defaultOrdering="companyGroup">Корректировки</SortableHeader>

                  {canManage ? <th scope="col"><span className="visually-hidden">Действия</span></th> : null}
                </tr>
              </thead>
              <tbody>
                {results.map((program) => (
                  <tr key={program.id}>
                    <td>
                      <Link className="text-link" to={`/developer-programs/${program.id}`}>
                        {program.companyGroupName}
                      </Link>
                      <small className="table-cell-note">{scopeName(program)}</small>
                    </td>
                    <td>
                      <strong>{program.bankName}</strong>
                      <small className="table-cell-note">{program.mortgageProgramName}</small>
                    </td>
                    <td>{valueOrDash(program.interestRate)}</td>
                    <td>
                      {program.gracePeriodMonths === null
                        ? '—'
                        : `${formatInteger(program.gracePeriodMonths)} мес.`}
                      <small className="table-cell-note">
                        {valueOrDash(program.gracePeriodInterestRate)}
                      </small>
                    </td>
                    <td>{valueOrDash(program.minimumInitialPaymentPercent)}</td>
                    <td>
                      {valueOrDash(program.maximumLoanAmount, formatCurrency)}
                      <small className="table-cell-note">
                        {program.maximumLoanTermYears === null
                          ? 'Срок не задан'
                          : `${formatInteger(program.maximumLoanTermYears)} лет`}
                      </small>
                    </td>
                    <td>
                      Удорожание: {valueOrDash(program.priceIncreasePercent)}
                      <small className="table-cell-note">
                        Дисконт: {valueOrDash(program.rateDiscountPercent)}
                      </small>
                    </td>

                    {canManage ? (
                      <td>
                        <div className="row-actions">
                          <Link
                            className="row-action"
                            to={`/developer-programs/${program.id}/edit`}
                            aria-label={`Редактировать: ${program.companyGroupName}, ${program.mortgageProgramName}`}
                          >✎</Link>
                          <button
                            className="row-action row-action--danger"
                            type="button"
                            aria-label={`Удалить: ${program.companyGroupName}, ${program.mortgageProgramName}`}
                            onClick={(event) => {
                              deleteMutation.reset()
                              deleteTriggerRef.current = event.currentTarget
                              setSelectedProgram(program)
                            }}
                          >×</button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScrollArea>
          <div className="property-mobile-list">
            {results.map((program) => (
              <article className="property-mobile-card" key={program.id}>
                <div className="property-mobile-card__heading">
                  <div>
                    <span>{program.bankName}</span>
                    <h2><Link className="text-link" to={`/developer-programs/${program.id}`}>
                      {program.companyGroupName}
                    </Link></h2>
                  </div>

                </div>
                <p className="mortgage-program-mobile-condition">
                  {scopeName(program)} · {program.mortgageProgramName}
                </p>
                <dl>
                  <div><dt>Ставка</dt><dd>{valueOrDash(program.interestRate)}</dd></div>
                  <div><dt>Первый взнос</dt><dd>{valueOrDash(program.minimumInitialPaymentPercent)}</dd></div>
                  <div><dt>Максимальная сумма</dt><dd>{valueOrDash(program.maximumLoanAmount, formatCurrency)}</dd></div>
                  <div><dt>Удорожание</dt><dd>{valueOrDash(program.priceIncreasePercent)}</dd></div>
                </dl>
                <div className="property-mobile-card__actions">
                  <Link className="text-link" to={`/developer-programs/${program.id}`}>Открыть</Link>
                  {canManage ? (
                    <Link className="text-link" to={`/developer-programs/${program.id}/edit`}>Редактировать</Link>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </>
      )}
      {totalPages > 1 ? (
        <Pagination label="Страницы программ застройщиков" page={page} totalPages={totalPages} onPageChange={(nextPage) => updateParameters({ page: String(nextPage) })} />
      ) : null}
      {selectedProgram ? (
        <ModalDialog labelledBy="developer-program-delete-title" describedBy="developer-program-delete-description" pending={deleteMutation.isPending} onClose={() => setSelectedProgram(null)}>
            <span className="eyebrow">Подтверждение</span>
            <h2 id="developer-program-delete-title">Удалить программу?</h2>
            <p id="developer-program-delete-description">
              Условия «{selectedProgram.companyGroupName} —{' '}
              {selectedProgram.mortgageProgramName}» будут удалены.
            </p>
            {deleteMutation.isError ? (
              <Notice as="p" tone="error" role="alert" className="form-error">
                Не удалось удалить программу. Повторите попытку.
              </Notice>
            ) : null}
            <div className="confirmation-dialog__actions">
              <button
                className="button button--secondary"
                type="button"
                ref={cancelButtonRef}
                disabled={deleteMutation.isPending}
                onClick={() => {
                  setSelectedProgram(null)
                  window.setTimeout(() => restoreFocus(deleteTriggerRef.current), 0)
                }}
              >Отмена</button>
              <button
                className="button button--danger"
                type="button"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(selectedProgram.id)}
              >{deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}</button>
            </div>
          </ModalDialog>
      ) : null}
    </div>
  )
}
