import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { Pagination } from '@/shared/ui/Pagination'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import {
  keyRateChartQueryOptions,
  keyRateListQueryOptions,
  sessionQueryOptions,
  synchronizeKeyRates,
} from '@/api/queries'
import { formatDate, formatInteger, formatPercent } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'
import { SortableHeader } from '@/shared/ui/SortableHeader'

import { KeyRateChart } from './KeyRateChart'

function formatRateChange(value: string | null) {
  if (value === null) return { className: '', label: '—' }
  const numericValue = Number(value)
  if (numericValue === 0) return { className: 'key-rate-change', label: '0 п.п.' }

  const increase = numericValue > 0
  const magnitude = formatPercent(String(Math.abs(numericValue))).replace('%', ' п.п.')
  return {
    className: `key-rate-change key-rate-change--${increase ? 'up' : 'down'}`,
    label: `${increase ? '↑' : '↓'} ${magnitude}`,
  }
}

export function KeyRatePage() {
  useDocumentTitle('Ключевая ставка')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const tableParameters = new URLSearchParams(searchParameters)
  tableParameters.delete('q')
  const keyRateQuery = useQuery(keyRateListQueryOptions(tableParameters))
  const chartQuery = useQuery(keyRateChartQueryOptions)
  const sessionQuery = useQuery(sessionQueryOptions)
  const queryClient = useQueryClient()
  const syncMutation = useMutation({
    mutationFn: synchronizeKeyRates,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['key-rates'] })
    },
  })

  const updatePage = (page: number) => {
    const nextParameters = new URLSearchParams(tableParameters)
    if (page <= 1) nextParameters.delete('page')
    else nextParameters.set('page', String(page))
    setSearchParameters(nextParameters)
  }

  if (keyRateQuery.isLoading) return <PageLoadingState />
  if (keyRateQuery.isError || !keyRateQuery.data) {
    return <ErrorState onRetry={() => void keyRateQuery.refetch()} />
  }

  const { page, results, totalCount, totalPages } = keyRateQuery.data
  const canSynchronize = sessionQuery.data?.capabilities.syncExternalData === true

  return (
    <div className="page-stack key-rate-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Финансовые справочники</span>
          <h1>Ключевая ставка</h1>
          <p>История ключевой ставки Банка России.</p>
        </div>
        {canSynchronize ? (
          <div className="page-header__actions">
            <button
              className="button button--primary"
              type="button"
              disabled={syncMutation.isPending}
              onClick={() => syncMutation.mutate()}
            >
              {syncMutation.isPending ? 'Обновляем…' : 'Обновить из ЦБ РФ'}
            </button>
          </div>
        ) : null}
      </header>

      <nav className="dictionary-tabs" aria-label="Разделы банков">
        <Link to="/banks">Банки</Link>
        <Link to="/mortgage-programs">Ипотечные программы</Link>
        <Link to="/developer-programs">Программы застройщиков</Link>
        <Link to="/key-rate" aria-current="page">Ключевая ставка</Link>
      </nav>

      {syncMutation.isSuccess ? (
        <p className="operation-message operation-message--success" role="status">
          Обработано {formatInteger(syncMutation.data.processed)}, добавлено{' '}
          {formatInteger(syncMutation.data.created)}, обновлено{' '}
          {formatInteger(syncMutation.data.updated)}.
        </p>
      ) : null}
      {syncMutation.isError ? (
        <p className="form-error" role="alert">
          Не удалось обновить ключевую ставку из ЦБ РФ. Повторите попытку позже.
        </p>
      ) : null}

      {chartQuery.data ? <KeyRateChart history={chartQuery.data} /> : null}
      {chartQuery.isError ? (
        <ErrorState
          title="Не удалось загрузить график ключевой ставки"
          onRetry={() => void chartQuery.refetch()}
        />
      ) : null}

      <div className="key-rate-history">
        <div className="results-heading" aria-live="polite">
          <p>Записей в истории <strong>{formatInteger(totalCount)}</strong></p>
          {keyRateQuery.isFetching ? <span>Обновляем…</span> : null}
        </div>

        {results.length === 0 ? (
          <EmptyState
            title="Данных о ключевой ставке пока нет"
            description={canSynchronize
              ? 'Загрузите историю решений с сайта Банка России.'
              : 'Администратор сможет загрузить историю из Банка России.'}
          />
        ) : (
          <TableScrollArea className="table-card property-table-wrapper" label="История ключевой ставки Банка России">
            <table className="property-table key-rate-table">
              <caption className="visually-hidden">История ключевой ставки Банка России</caption>
              <thead>
                <tr>
                  <SortableHeader field="meetingDate" defaultOrdering="-meetingDate">Дата</SortableHeader>
                  <SortableHeader field="keyRate" defaultOrdering="-meetingDate">Ставка</SortableHeader>
                  <SortableHeader field="rateChange" defaultOrdering="-meetingDate">Изменение</SortableHeader>
                </tr>
              </thead>
              <tbody>
                {results.map((keyRate) => {
                  const rateChange = formatRateChange(keyRate.rateChange)
                  return (
                    <tr key={keyRate.id}>
                      <td>{formatDate(keyRate.meetingDate)}</td>
                      <td><strong>{formatPercent(keyRate.keyRate)}</strong></td>
                      <td><span className={rateChange.className}>{rateChange.label}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </TableScrollArea>
        )}

        {totalPages > 1 ? (
          <Pagination label="Страницы истории ключевой ставки" page={page} totalPages={totalPages} onPageChange={updatePage} />
        ) : null}
      </div>
    </div>
  )
}
