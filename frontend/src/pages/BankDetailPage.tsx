import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  bankDetailQueryOptions,
  deleteBank,
  sessionQueryOptions,
} from '@/api/queries'
import { formatDateTime, formatPercent } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

export function BankDetailPage() {
  const { bankId } = useParams()
  const bankIdentifier = Number(bankId)
  const hasValidIdentifier = (
    Number.isInteger(bankIdentifier) && bankIdentifier > 0
  )
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const sessionQuery = useQuery(sessionQueryOptions)
  const bankQuery = useQuery({
    ...bankDetailQueryOptions(bankIdentifier),
    enabled: hasValidIdentifier,
  })
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const deleteTriggerRef = useRef<HTMLButtonElement>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: () => deleteBank(bankIdentifier),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['banks'] })
      queryClient.removeQueries({ queryKey: ['bank', bankIdentifier] })
      navigate('/banks')
    },
  })
  useDocumentTitle(bankQuery.data?.name ?? 'Карточка банка')

  useEffect(() => {
    if (!isDeleteDialogOpen) return
    cancelButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleteMutation.isPending) {
        setIsDeleteDialogOpen(false)
        window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [deleteMutation.isPending, isDeleteDialogOpen])

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Банк не найден"
        description="Проверьте адрес или вернитесь к списку банков."
        action={(
          <Link className="button button--secondary" to="/banks">
            К списку
          </Link>
        )}
      />
    )
  }
  if (bankQuery.isLoading) return <PageLoadingState />
  if (bankQuery.isError || !bankQuery.data) {
    return (
      <ErrorState
        title="Банк не найден или недоступен"
        onRetry={() => void bankQuery.refetch()}
      />
    )
  }

  const bank = bankQuery.data
  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )

  return (
    <div className="page-stack bank-detail-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Карточка банка</span>
          <h1>{bank.name}</h1>
          <p>
            Полные условия ипотечных программ банка для расчётов и
            консультаций.
          </p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to="/banks">
            К списку
          </Link>
          {canManageCatalogs ? (
            <>
              <Link
                className="button button--secondary"
                to={`/banks/${bank.id}/edit`}
              >
                Редактировать
              </Link>
              <button
                className="button button--danger"
                type="button"
                ref={deleteTriggerRef}
                onClick={() => {
                  deleteMutation.reset()
                  setIsDeleteDialogOpen(true)
                }}
              >
                Удалить
              </button>
            </>
          ) : null}
        </div>
      </header>

      <section className="bank-summary-card">
        <div className="bank-summary-card__logo" aria-hidden="true">
          {bank.logoUrl ? (
            <img
              src={bank.logoUrl}
              alt=""
              referrerPolicy="no-referrer"
            />
          ) : bank.name.slice(0, 1).toUpperCase()}
        </div>
        <div>
          <span className={bank.isActive
            ? 'catalog-status'
            : 'catalog-status catalog-status--inactive'}>
            {bank.isActive ? 'Активен' : 'Неактивен'}
          </span>
          <h2>{bank.name}</h2>
          <p>
            {bank.programs.length
              ? `Доступно программ: ${bank.programs.length}`
              : 'Ипотечные программы пока не добавлены.'}
          </p>
        </div>
      </section>

      <section
        className="saved-property-card"
        aria-labelledby="bank-programs-title"
      >
        <div className="section-heading">
          <div>
            <span className="eyebrow">Условия кредитования</span>
            <h2 id="bank-programs-title">Ипотечные программы</h2>
          </div>
        </div>
        {bank.programs.length ? (
          <>
            <div className="property-table-wrapper">
              <table className="property-table bank-program-table">
                <caption className="visually-hidden">
                  Ипотечные программы банка {bank.name}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Программа</th>
                    <th scope="col">Ставка</th>
                    <th scope="col">Первый взнос</th>
                    <th scope="col">Макс. срок</th>
                  </tr>
                </thead>
                <tbody>
                  {bank.programs.map((program) => (
                    <tr key={program.id}>
                      <td><strong>{program.mortgageProgramName}</strong></td>
                      <td>{formatPercent(program.interestRate)}</td>
                      <td>
                        {formatPercent(program.minimumInitialPaymentPercent)}
                      </td>
                      <td>
                        {program.maximumLoanTermYears
                          ? `${program.maximumLoanTermYears} лет`
                          : 'Не ограничен'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="property-mobile-list bank-program-mobile-list">
              {bank.programs.map((program) => (
                <article className="property-mobile-card" key={program.id}>
                  <div className="property-mobile-card__heading">
                    <div>
                      <span>Программа</span>
                      <h2>{program.mortgageProgramName}</h2>
                    </div>
                    <strong>{formatPercent(program.interestRate)}</strong>
                  </div>
                  <dl>
                    <div>
                      <dt>Первый взнос</dt>
                      <dd>
                        {formatPercent(program.minimumInitialPaymentPercent)}
                      </dd>
                    </div>
                    <div>
                      <dt>Макс. срок</dt>
                      <dd>
                        {program.maximumLoanTermYears
                          ? `${program.maximumLoanTermYears} лет`
                          : 'Не ограничен'}
                      </dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          </>
        ) : (
          <p className="complex-copy">У банка нет добавленных программ.</p>
        )}
      </section>

      <section
        className="property-system-information"
        aria-label="Системная информация"
      >
        <span>Создано: {formatDateTime(bank.createdAt)}</span>
        <span>Обновлено: {formatDateTime(bank.updatedAt)}</span>
      </section>
      <p className="legacy-fallback">
        Нужен прежний экран?{' '}
        <a className="text-link" href={bank.legacyDetailUrl}>
          Открыть Django-версию
        </a>
      </p>

      {isDeleteDialogOpen ? (
        <div
          className="confirmation-dialog-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (
              event.currentTarget === event.target
              && !deleteMutation.isPending
            ) {
              setIsDeleteDialogOpen(false)
            }
          }}
        >
          <section
            className="confirmation-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="bank-detail-delete-title"
            aria-describedby="bank-detail-delete-description"
          >
            <span className="eyebrow">Подтверждение</span>
            <h2 id="bank-detail-delete-title">Удалить банк?</h2>
            <p id="bank-detail-delete-description">
              «{bank.name}» и его банковские условия будут удалены.
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
                onClick={() => setIsDeleteDialogOpen(false)}
              >
                Отмена
              </button>
              <button
                className="button button--danger"
                type="button"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
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
