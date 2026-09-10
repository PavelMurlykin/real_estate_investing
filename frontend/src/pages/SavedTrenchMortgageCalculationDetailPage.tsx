import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  deleteSavedTrenchMortgageCalculation,
  savedTrenchMortgageCalculationDetailQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import { TrenchMortgageResult } from '@/features/mortgage/TrenchMortgageResult'
import {
  formatArea,
  formatCurrency,
  formatDateTime,
  formatPercent,
} from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

export function SavedTrenchMortgageCalculationDetailPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { calculationId = '' } = useParams()
  const calculationIdentifier = Number(calculationId)
  const hasValidIdentifier = Number.isInteger(calculationIdentifier)
    && calculationIdentifier > 0
  const sessionQuery = useQuery(sessionQueryOptions)
  const calculationQuery = useQuery({
    ...savedTrenchMortgageCalculationDetailQueryOptions(calculationIdentifier),
    enabled: sessionQuery.data?.isAuthenticated === true && hasValidIdentifier,
  })
  const [isDeleteConfirmationOpen, setIsDeleteConfirmationOpen] = useState(false)
  const deleteTriggerRef = useRef<HTMLButtonElement>(null)
  const deleteConfirmRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: () => deleteSavedTrenchMortgageCalculation(
      calculationIdentifier,
    ),
    onSuccess: async () => {
      queryClient.removeQueries({
        queryKey: [
          'saved-trench-mortgage-calculation',
          calculationIdentifier,
        ],
        exact: true,
      })
      await queryClient.invalidateQueries({
        queryKey: ['saved-trench-mortgage-calculations'],
      })
      navigate('/mortgage/trench/calculations', { replace: true })
    },
  })
  useDocumentTitle(
    calculationQuery.data
      ? `Траншевый расчёт от ${formatDateTime(
        calculationQuery.data.createdAt,
      )}`
      : 'Детали траншевого расчёта',
  )

  useEffect(() => {
    if (!isDeleteConfirmationOpen) return
    deleteConfirmRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setIsDeleteConfirmationOpen(false)
      window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isDeleteConfirmationOpen])

  const closeDeleteConfirmation = () => {
    setIsDeleteConfirmationOpen(false)
    deleteMutation.reset()
    window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
  }

  if (sessionQuery.isLoading) return <PageLoadingState />

  if (!sessionQuery.data?.isAuthenticated) {
    return (
      <div className="page-stack">
        <header className="page-header">
          <div>
            <span className="eyebrow">Личный раздел</span>
            <h1>Детали траншевого расчёта</h1>
          </div>
        </header>
        <EmptyState
          title="Войдите, чтобы открыть расчёт"
          description="Доступ к сохранённому сценарию проверяется на сервере."
          action={(
            <a
              className="button button--primary"
              href={`/users/login/?next=${encodeURIComponent(
                `/app/mortgage/trench/calculations/${calculationId}`,
              )}`}
            >
              Войти
            </a>
          )}
        />
      </div>
    )
  }

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Расчёт не найден"
        description="Проверьте адрес или вернитесь к истории расчётов."
        action={(
          <Link
            className="button button--secondary"
            to="/mortgage/trench/calculations"
          >
            К истории
          </Link>
        )}
      />
    )
  }
  if (calculationQuery.isLoading) return <PageLoadingState />
  if (calculationQuery.isError || !calculationQuery.data) {
    return (
      <ErrorState
        title="Расчёт не найден или недоступен"
        onRetry={() => void calculationQuery.refetch()}
      />
    )
  }

  const savedCalculation = calculationQuery.data
  const property = savedCalculation.property
  const assumptions = savedCalculation.calculation.assumptions

  return (
    <div className="page-stack saved-calculation-detail">
      <header className="page-header">
        <div>
          <span className="eyebrow">Сохранённый сценарий</span>
          <h1>
            Траншевый расчёт от{' '}
            {formatDateTime(savedCalculation.createdAt)}
          </h1>
          <p>
            {property.city}, {property.realEstateComplex}, квартира{' '}
            {property.apartmentNumber}
          </p>
        </div>
        <div className="page-header__actions">
          <Link
            className="button button--secondary"
            to="/mortgage/trench/calculations"
          >
            К истории
          </Link>
          <a
            className="button button--secondary"
            href={`/api/v1/mortgage/trench/calculations/${
              savedCalculation.id
            }/export/excel/`}
          >
            Excel
          </a>
          <a
            className="button button--secondary"
            href={`/api/v1/mortgage/trench/calculations/${
              savedCalculation.id
            }/export/word/`}
          >
            Word
          </a>
          <Link
            className="button button--primary"
            to={`/mortgage/trench?sample=${savedCalculation.id}`}
          >
            Новый по образцу
          </Link>
          <button
            className="button button--danger"
            type="button"
            ref={deleteTriggerRef}
            onClick={() => setIsDeleteConfirmationOpen(true)}
          >
            Удалить
          </button>
        </div>
      </header>

      {isDeleteConfirmationOpen ? (
        <section
          className="delete-confirmation"
          role="alertdialog"
          aria-labelledby="delete-trench-calculation-title"
          aria-describedby="delete-trench-calculation-description"
        >
          <div>
            <h2 id="delete-trench-calculation-title">
              Удалить сохранённый траншевый расчёт?
            </h2>
            <p id="delete-trench-calculation-description">
              Запись, транши и параметры исчезнут из истории. Это действие
              нельзя отменить.
            </p>
            {deleteMutation.isError ? (
              <p className="form-error" role="alert">
                Не удалось удалить расчёт. Повторите попытку.
              </p>
            ) : null}
          </div>
          <div className="delete-confirmation__actions">
            <button
              className="button button--secondary"
              type="button"
              disabled={deleteMutation.isPending}
              onClick={closeDeleteConfirmation}
            >
              Отмена
            </button>
            <button
              className="button button--danger"
              type="button"
              ref={deleteConfirmRef}
              disabled={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
            >
              {deleteMutation.isPending ? 'Удаляем…' : 'Удалить расчёт'}
            </button>
          </div>
        </section>
      ) : null}

      <section
        className="saved-property-card"
        aria-labelledby="saved-trench-property-title"
      >
        <div className="section-heading section-heading--with-action">
          <div>
            <span className="eyebrow">Объект недвижимости</span>
            <h2 id="saved-trench-property-title">
              {property.realEstateComplex}
            </h2>
          </div>
          <Link className="text-link" to={`/properties/${property.id}`}>
            Открыть объект <span aria-hidden="true">→</span>
          </Link>
        </div>
        <dl className="saved-property-grid">
          <div><dt>Застройщик</dt><dd>{property.developer}</dd></div>
          <div><dt>Класс ЖК</dt><dd>{property.realEstateClass}</dd></div>
          <div>
            <dt>Корпус / квартира</dt>
            <dd>{property.building} / {property.apartmentNumber}</dd>
          </div>
          <div><dt>Планировка</dt><dd>{property.layout}</dd></div>
          <div>
            <dt>Площадь / этаж</dt>
            <dd>{formatArea(property.area)} / {property.floor}</dd>
          </div>
          <div><dt>Отделка</dt><dd>{property.decoration}</dd></div>
          <div>
            <dt>Базовая стоимость</dt>
            <dd>{formatCurrency(assumptions.basePropertyCost)}</dd>
          </div>
          <div>
            <dt>
              {assumptions.priceAdjustmentType === 'discount'
                ? 'Скидка'
                : 'Удорожание'}
            </dt>
            <dd>
              {formatPercent(assumptions.priceAdjustmentPercent)} ·{' '}
              {formatCurrency(assumptions.priceAdjustmentRubles)}
            </dd>
          </div>
        </dl>
      </section>

      <TrenchMortgageResult result={savedCalculation.calculation} />

      <p className="legacy-fallback">
        Нужен прежний экран?{' '}
        <a className="text-link" href={savedCalculation.legacyDetailUrl}>
          Открыть Django-версию
        </a>
      </p>
    </div>
  )
}
