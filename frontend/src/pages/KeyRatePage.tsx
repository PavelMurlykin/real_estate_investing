import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import {
  keyRateListQueryOptions,
  sessionQueryOptions,
  synchronizeKeyRates,
} from '@/api/queries'
import { formatDate, formatDateTime, formatInteger, formatPercent } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

function formatRateChange(value: string | null) {
  if (value === null) return { className: '', label: '—' }
  const numericValue = Number(value)
  if (numericValue > 0) {
    return {
      className: 'key-rate-change key-rate-change--up',
      label: `↑ ${formatPercent(String(Math.abs(numericValue)))}`,
    }
  }
  if (numericValue < 0) {
    return {
      className: 'key-rate-change key-rate-change--down',
      label: `↓ ${formatPercent(String(Math.abs(numericValue)))}`,
    }
  }
  return { className: 'key-rate-change', label: formatPercent('0') }
}

export function KeyRatePage() {
  useDocumentTitle('Ключевая ставка')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const keyRateQuery = useQuery(keyRateListQueryOptions(searchParameters))
  const sessionQuery = useQuery(sessionQueryOptions)
  const queryClient = useQueryClient()
  const syncMutation = useMutation({
    mutationFn: synchronizeKeyRates,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['key-rates'] })
    },
  })

  const updatePage = (page: number) => {
    const nextParameters = new URLSearchParams(searchParameters)
    if (page <= 1) nextParameters.delete('page')
    else nextParameters.set('page', String(page))
    setSearchParameters(nextParameters)
  }

  if (keyRateQuery.isLoading) return <PageLoadingState />
  if (keyRateQuery.isError || !keyRateQuery.data) {
    return <ErrorState onRetry={() => void keyRateQuery.refetch()} />
  }

  const {
    currentRate,
    lastSyncedAt,
    legacyUrl,
    page,
    results,
    totalCount,
    totalPages,
  } = keyRateQuery.data
  const canSynchronize = (
    sessionQuery.data?.capabilities.syncExternalData === true
  )

  return (
    <div className="page-stack key-rate-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Финансовые справочники</span>
          <h1>Ключевая ставка</h1>
          <p>
            Актуальная ставка Банка России и история её изменений по датам
            решений регулятора.
          </p>
        </div>
        <div className="page-header__actions">
          <a className="button button--secondary" href={legacyUrl}>
            Прежняя версия
          </a>
          {canSynchronize ? (
            <button
              className="button button--primary"
              type="button"
              disabled={syncMutation.isPending}
              onClick={() => syncMutation.mutate()}
            >
              {syncMutation.isPending ? 'Обновляем…' : 'Обновить из ЦБ РФ'}
            </button>
          ) : null}
        </div>
      </header>

      <nav className="dictionary-tabs" aria-label="Разделы банков">
        <Link to="/banks">Банки</Link>
        <Link to="/mortgage-programs">Ипотечные программы</Link>
        <Link to="/developer-programs">Программы застройщиков</Link>
        <Link to="/key-rate" aria-current="page">Ключевая ставка</Link>
      </nav>

      <section className="key-rate-summary" aria-label="Текущая ключевая ставка">
        <div className="key-rate-summary__value">
          <span>Текущая ставка</span>
          <strong>{currentRate ? formatPercent(currentRate.keyRate) : '—'}</strong>
          <small>
            {currentRate
              ? `Действует с ${formatDate(currentRate.meetingDate)}`
              : 'Данные ещё не загружены'}
          </small>
        </div>
        <dl className="key-rate-summary__meta">
          <div>
            <dt>Записей в истории</dt>
            <dd>{formatInteger(totalCount)}</dd>
          </div>
          <div>
            <dt>Последнее изменение данных</dt>
            <dd>{lastSyncedAt ? formatDateTime(lastSyncedAt) : '—'}</dd>
          </div>
        </dl>
      </section>

      {syncMutation.isSuccess ? (
        <p className="operation-message operation-message--success" role="status">
          Синхронизация завершена: обработано{' '}
          {formatInteger(syncMutation.data.processed)}, добавлено{' '}
          {formatInteger(syncMutation.data.created)}, обновлено{' '}
          {formatInteger(syncMutation.data.updated)}.
        </p>
      ) : null}
      {syncMutation.isError ? (
        <p className="form-error" role="alert">
          Не удалось обновить ключевую ставку из ЦБ РФ. Повторите попытку позже.
        </p>
      ) : null}

      <div className="results-heading" aria-live="polite">
        <p>История решений: <strong>{formatInteger(totalCount)}</strong></p>
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
        <>
          <div className="table-card property-table-wrapper">
            <table className="property-table catalog-table key-rate-table">
              <caption className="visually-hidden">
                История изменений ключевой ставки Банка России
              </caption>
              <thead>
                <tr>
                  <th scope="col">Дата решения</th>
                  <th scope="col">Ключевая ставка</th>
                  <th scope="col">Изменение</th>
                  <th scope="col">Статус</th>
                </tr>
              </thead>
              <tbody>
                {results.map((keyRate) => {
                  const rateChange = formatRateChange(keyRate.rateChange)
                  return (
                    <tr key={keyRate.id}>
                      <td>{formatDate(keyRate.meetingDate)}</td>
                      <td><strong>{formatPercent(keyRate.keyRate)}</strong></td>
                      <td>
                        <span className={rateChange.className}>
                          {rateChange.label}
                        </span>
                      </td>
                      <td>
                        <span className={keyRate.isActive
                          ? 'catalog-status'
                          : 'catalog-status catalog-status--inactive'}>
                          {keyRate.isActive ? 'Используется' : 'Неактивна'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="property-mobile-list key-rate-mobile-list">
            {results.map((keyRate) => {
              const rateChange = formatRateChange(keyRate.rateChange)
              return (
                <article className="property-mobile-card" key={keyRate.id}>
                  <div className="property-mobile-card__heading">
                    <div>
                      <span>Решение от {formatDate(keyRate.meetingDate)}</span>
                      <h2>{formatPercent(keyRate.keyRate)}</h2>
                    </div>
                    <span className={keyRate.isActive
                      ? 'catalog-status'
                      : 'catalog-status catalog-status--inactive'}>
                      {keyRate.isActive ? 'Используется' : 'Неактивна'}
                    </span>
                  </div>
                  <dl>
                    <div>
                      <dt>Изменение</dt>
                      <dd className={rateChange.className}>{rateChange.label}</dd>
                    </div>
                    <div>
                      <dt>Запись обновлена</dt>
                      <dd>{formatDateTime(keyRate.updatedAt)}</dd>
                    </div>
                  </dl>
                </article>
              )
            })}
          </div>
        </>
      )}

      {totalPages > 1 ? (
        <nav className="pagination" aria-label="Страницы истории ключевой ставки">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => updatePage(page - 1)}
          >
            <span aria-hidden="true">←</span> Назад
          </button>
          <span>Страница <strong>{page}</strong> из {totalPages}</span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => updatePage(page + 1)}
          >
            Далее <span aria-hidden="true">→</span>
          </button>
        </nav>
      ) : null}
    </div>
  )
}
