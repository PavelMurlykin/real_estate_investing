import { Notice } from '@/shared/ui/Notice'
import { ModalDialog } from '@/shared/ui/ModalDialog'
import { InteractiveTable } from '@/shared/ui/InteractiveTable'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
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
    <div className="page-stack bank-detail-page detail-page">
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

      <section className="bank-summary-card detail-card detail-card--accent">
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
        className="saved-property-card detail-card"
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
              <InteractiveTable rows={bank.programs} getRowKey={(program) => program.id}
              caption={`Ипотечные программы банка ${bank.name}`} className="property-table bank-program-table"
              columns={[
                { id: 'column0', label: "Программа", value: (program) => program.mortgageProgramName, render: (program) => <><strong>{program.mortgageProgramName}</strong></> },
                { id: 'column1', label: "Ставка", value: (program) => Number(program.interestRate), searchValue: (program) => formatPercent(program.interestRate), render: (program) => <>{formatPercent(program.interestRate)}</> },
                { id: 'column2', label: "Первый взнос", value: (program) => Number(program.minimumInitialPaymentPercent), searchValue: (program) => formatPercent(program.minimumInitialPaymentPercent), render: (program) => <>{formatPercent(program.minimumInitialPaymentPercent)}</> },
                { id: 'column3', label: "Макс. срок", value: (program) => program.maximumLoanTermYears, render: (program) => <>{program.maximumLoanTermYears
                          ? `${program.maximumLoanTermYears} лет`
                          : 'Не ограничен'}</> },
              ]} />
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
      {isDeleteDialogOpen ? (
        <ModalDialog labelledBy="bank-detail-delete-title" describedBy="bank-detail-delete-description" pending={deleteMutation.isPending} onClose={() => setIsDeleteDialogOpen(false)}>
            <span className="eyebrow">Подтверждение</span>
            <h2 id="bank-detail-delete-title" tabIndex={-1}>Удалить банк?</h2>
            <p id="bank-detail-delete-description">
              «{bank.name}» и его банковские условия будут удалены.
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
          </ModalDialog>
      ) : null}
    </div>
  )
}
