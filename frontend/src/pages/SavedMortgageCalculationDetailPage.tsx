import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import {
  savedMortgageCalculationDetailQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import { MortgageResult } from '@/features/mortgage/MortgageResult'
import {
  formatArea,
  formatCurrency,
  formatDateTime,
  formatPercent,
} from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

export function SavedMortgageCalculationDetailPage() {
  const { calculationId = '' } = useParams()
  const calculationIdentifier = Number(calculationId)
  const hasValidIdentifier = Number.isInteger(calculationIdentifier)
    && calculationIdentifier > 0
  const sessionQuery = useQuery(sessionQueryOptions)
  const calculationQuery = useQuery({
    ...savedMortgageCalculationDetailQueryOptions(calculationIdentifier),
    enabled: sessionQuery.data?.isAuthenticated === true && hasValidIdentifier,
  })
  useDocumentTitle(
    calculationQuery.data
      ? `Расчёт от ${formatDateTime(calculationQuery.data.createdAt)}`
      : 'Детали расчёта ипотеки',
  )

  if (sessionQuery.isLoading) return <PageLoadingState />

  if (!sessionQuery.data?.isAuthenticated) {
    return (
      <div className="page-stack">
        <header className="page-header">
          <div>
            <span className="eyebrow">Личный раздел</span>
            <h1>Детали расчёта ипотеки</h1>
          </div>
        </header>
        <EmptyState
          title="Войдите, чтобы открыть расчёт"
          description="Доступ к сохранённому сценарию проверяется на сервере."
          action={(
            <a
              className="button button--primary"
              href={`/users/login/?next=${encodeURIComponent(`/app/mortgage/calculations/${calculationId}`)}`}
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
          <Link className="button button--secondary" to="/mortgage/calculations">
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
          <h1>Расчёт от {formatDateTime(savedCalculation.createdAt)}</h1>
          <p>{property.city}, {property.realEstateComplex}, квартира {property.apartmentNumber}</p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to="/mortgage/calculations">
            К истории
          </Link>
          <a className="button button--secondary" href={savedCalculation.legacyDetailUrl}>
            Экспорт в прежней версии
          </a>
          <a className="button button--primary" href={savedCalculation.legacySampleUrl}>
            Новый по образцу
          </a>
        </div>
      </header>

      <section className="saved-property-card" aria-labelledby="saved-property-title">
        <div className="section-heading section-heading--with-action">
          <div>
            <span className="eyebrow">Объект недвижимости</span>
            <h2 id="saved-property-title">{property.realEstateComplex}</h2>
          </div>
          <a className="text-link" href={property.detailUrl}>
            Открыть объект <span aria-hidden="true">→</span>
          </a>
        </div>
        <dl className="saved-property-grid">
          <div><dt>Застройщик</dt><dd>{property.developer}</dd></div>
          <div><dt>Класс ЖК</dt><dd>{property.realEstateClass}</dd></div>
          <div><dt>Корпус / квартира</dt><dd>{property.building} / {property.apartmentNumber}</dd></div>
          <div><dt>Планировка</dt><dd>{property.layout}</dd></div>
          <div><dt>Площадь / этаж</dt><dd>{formatArea(property.area)} / {property.floor}</dd></div>
          <div><dt>Отделка</dt><dd>{property.decoration}</dd></div>
          <div><dt>Базовая стоимость</dt><dd>{formatCurrency(assumptions.basePropertyCost)}</dd></div>
          <div>
            <dt>{assumptions.priceAdjustmentType === 'discount' ? 'Скидка' : 'Удорожание'}</dt>
            <dd>{formatPercent(assumptions.priceAdjustmentPercent)} · {formatCurrency(assumptions.priceAdjustmentRubles)}</dd>
          </div>
        </dl>
      </section>

      <MortgageResult result={savedCalculation.calculation} />
    </div>
  )
}
