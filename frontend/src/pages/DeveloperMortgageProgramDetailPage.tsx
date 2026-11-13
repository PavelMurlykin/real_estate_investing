import { Notice } from '@/shared/ui/Notice'
import { ModalDialog } from '@/shared/ui/ModalDialog'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  deleteDeveloperMortgageProgram,
  developerMortgageProgramDetailQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import { formatCurrency, formatDateTime, formatInteger, formatPercent } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

function optionalPercent(value: string | null) {
  return value === null ? 'Не задано' : formatPercent(value)
}

export function DeveloperMortgageProgramDetailPage() {
  const { developerProgramId } = useParams()
  const identifier = Number(developerProgramId)
  const hasValidIdentifier = Number.isInteger(identifier) && identifier > 0
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const sessionQuery = useQuery(sessionQueryOptions)
  const programQuery = useQuery({
    ...developerMortgageProgramDetailQueryOptions(identifier),
    enabled: hasValidIdentifier,
  })
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const deleteTriggerRef = useRef<HTMLButtonElement>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: () => deleteDeveloperMortgageProgram(identifier),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['developer-mortgage-programs'],
      })
      queryClient.removeQueries({
        queryKey: ['developer-mortgage-program', identifier],
      })
      navigate('/developer-programs')
    },
  })
  useDocumentTitle(
    programQuery.data
      ? `${programQuery.data.companyGroupName} — ${programQuery.data.mortgageProgramName}`
      : 'Программа застройщика',
  )

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Программа застройщика не найдена"
        description="Проверьте адрес или вернитесь к списку."
        action={<Link className="button button--secondary" to="/developer-programs">К списку</Link>}
      />
    )
  }
  if (programQuery.isLoading) return <PageLoadingState />
  if (programQuery.isError || !programQuery.data) {
    return (
      <ErrorState
        title="Программа застройщика не найдена или недоступна"
        onRetry={() => programQuery.refetch()}
      />
    )
  }

  const program = programQuery.data
  const canManage = sessionQuery.data?.capabilities.manageCatalogs === true
  return (
    <div className="page-stack developer-program-detail-page detail-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Карточка программы застройщика</span>
          <h1>{program.companyGroupName}</h1>
          <p>{program.mortgageProgramName} · {program.bankName}</p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to="/developer-programs">К списку</Link>
          {canManage ? (
            <>
              <Link className="button button--secondary" to={`/developer-programs/${program.id}/edit`}>
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
              >Удалить</button>
            </>
          ) : null}
        </div>
      </header>

      <section className="developer-program-summary-card detail-card detail-card--accent">
        <div>
          <span className={program.isActive
            ? 'catalog-status'
            : 'catalog-status catalog-status--inactive'}>
            {program.isActive ? 'Активна' : 'На стопе'}
          </span>
          <h2>{program.mortgageProgramName}</h2>
          <p>
            {program.realEstateComplexName
              ? `${program.realEstateComplexName} · ${program.complexDeveloperName}`
              : 'Действует для всех жилых комплексов группы'}
          </p>
        </div>
        <div className="developer-program-summary-card__bank">
          <span>Банк</span>
          <strong>{program.bankName}</strong>
        </div>
      </section>

      <section className="saved-property-card detail-card" aria-labelledby="developer-program-conditions">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Финансовые параметры</span>
            <h2 id="developer-program-conditions">Условия кредитования</h2>
          </div>
        </div>
        <dl className="property-detail-facts developer-program-facts">
          <div>
            <dt>Годовая ставка</dt>
            <dd>{optionalPercent(program.interestRate)}</dd>
          </div>
          <div>
            <dt>Первоначальный взнос</dt>
            <dd>{optionalPercent(program.minimumInitialPaymentPercent)}</dd>
          </div>
          <div>
            <dt>Максимальная сумма</dt>
            <dd>{program.maximumLoanAmount === null
              ? 'Не задана'
              : formatCurrency(program.maximumLoanAmount)}</dd>
          </div>
          <div>
            <dt>Максимальный срок</dt>
            <dd>{program.maximumLoanTermYears === null
              ? 'Не задан'
              : `${formatInteger(program.maximumLoanTermYears)} лет`}</dd>
          </div>
          <div>
            <dt>Льготный период</dt>
            <dd>{program.gracePeriodMonths === null
              ? 'Не задан'
              : `${formatInteger(program.gracePeriodMonths)} мес.`}</dd>
          </div>
          <div>
            <dt>Ставка льготного периода</dt>
            <dd>{optionalPercent(program.gracePeriodInterestRate)}</dd>
          </div>
          <div>
            <dt>Удорожание</dt>
            <dd>{optionalPercent(program.priceIncreasePercent)}</dd>
          </div>
          <div>
            <dt>Дисконт к ставке</dt>
            <dd>{optionalPercent(program.rateDiscountPercent)}</dd>
          </div>
        </dl>
      </section>
      <section className="property-system-information" aria-label="Системная информация">
        <span>Создано: {formatDateTime(program.createdAt)}</span>
        <span>Обновлено: {formatDateTime(program.updatedAt)}</span>
      </section>

      {isDeleteDialogOpen ? (
        <ModalDialog labelledBy="developer-program-detail-delete-title" describedBy="developer-program-detail-delete-description" pending={deleteMutation.isPending} onClose={() => setIsDeleteDialogOpen(false)}>
            <span className="eyebrow">Подтверждение</span>
            <h2 id="developer-program-detail-delete-title" tabIndex={-1}>Удалить программу?</h2>
            <p id="developer-program-detail-delete-description">
              Условия «{program.companyGroupName} — {program.mortgageProgramName}» будут удалены.
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
                onClick={() => setIsDeleteDialogOpen(false)}
              >Отмена</button>
              <button
                className="button button--danger"
                type="button"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
              >{deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}</button>
            </div>
          </ModalDialog>
      ) : null}
    </div>
  )
}
