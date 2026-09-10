import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import {
  customerDetailQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import { formatArea, formatCurrency, formatDate, formatDateTime, formatPercent } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

function formatOptionalCurrency(value: string | null) {
  return value ? formatCurrency(value) : '—'
}

function formatOptionalArea(value: string | null) {
  return value ? formatArea(value) : '—'
}

function formatBoolean(value: boolean | null) {
  if (value === null) return '—'
  return value ? 'Да' : 'Нет'
}

export function CustomerDetailPage() {
  const { customerId = '' } = useParams()
  const customerIdentifier = Number(customerId)
  const hasValidIdentifier = Number.isInteger(customerIdentifier)
    && customerIdentifier > 0
  const sessionQuery = useQuery(sessionQueryOptions)
  const customerQuery = useQuery({
    ...customerDetailQueryOptions(customerIdentifier),
    enabled: hasValidIdentifier
      && sessionQuery.data?.isAuthenticated === true,
  })
  useDocumentTitle(
    customerQuery.data?.fullName
      ? `Клиент: ${customerQuery.data.fullName}`
      : 'Карточка клиента',
  )

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Клиент не найден"
        description="Проверьте адрес или вернитесь к списку клиентов."
        action={(
          <Link className="button button--secondary" to="/customers">
            К списку клиентов
          </Link>
        )}
      />
    )
  }

  if (sessionQuery.isLoading) return <PageLoadingState />

  if (!sessionQuery.data?.isAuthenticated) {
    const nextPath = `/app/customers/${customerIdentifier}`
    return (
      <EmptyState
        title="Войдите, чтобы открыть карточку клиента"
        description="Персональные и финансовые данные защищены авторизацией."
        action={(
          <a
            className="button button--primary"
            href={`/users/login/?next=${encodeURIComponent(nextPath)}`}
          >
            Войти
          </a>
        )}
      />
    )
  }

  if (customerQuery.isLoading) return <PageLoadingState />
  if (customerQuery.isError || !customerQuery.data) {
    return (
      <ErrorState
        title="Клиент не найден или недоступен"
        onRetry={() => void customerQuery.refetch()}
      />
    )
  }

  const customer = customerQuery.data
  const customerName = customer.fullName || `Клиент #${customer.id}`
  const birthValue = customer.birthDate
    ? formatDate(customer.birthDate)
    : customer.birthYear?.toString() || '—'

  return (
    <div className="page-stack customer-detail-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Карточка клиента</span>
          <h1>{customerName}</h1>
          <p>
            {customer.residenceCity || 'Город проживания не указан'}
            {' · '}
            {customer.isActive ? 'Активный клиент' : 'Неактивный клиент'}
          </p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to="/customers">
            К списку
          </Link>
          <Link
            className="button button--secondary"
            to={`/customers/${customer.id}/edit`}
          >
            Редактировать
          </Link>
          <a className="button button--danger" href={customer.legacyDeleteUrl}>
            Удалить
          </a>
        </div>
      </header>

      <section
        className="customer-capacity-card"
        aria-labelledby="customer-capacity-title"
      >
        <div>
          <span className="eyebrow">Предварительная оценка</span>
          <h2 id="customer-capacity-title">Финансовый потенциал</h2>
          <strong className="customer-capacity-card__amount">
            {customer.calculated.maximumPropertyCost
              ? formatCurrency(customer.calculated.maximumPropertyCost)
              : 'Недостаточно данных'}
          </strong>
          <p>Оценка при рыночной ставке без учёта дополнительных расходов.</p>
        </div>
        <dl className="customer-capacity-card__metrics">
          <div>
            <dt>Расчётная ставка</dt>
            <dd>{formatPercent(customer.calculated.annualRate)}</dd>
          </div>
          <div>
            <dt>Ключевая ставка</dt>
            <dd>{formatPercent(customer.calculated.actualKeyRate)}</dd>
          </div>
          <div>
            <dt>Максимальный срок</dt>
            <dd>{customer.calculated.maximumTermYears} лет</dd>
          </div>
        </dl>
        <a className="button button--primary" href={customer.legacyMortgageUrl}>
          Рассчитать ипотеку
        </a>
      </section>

      {customer.calculated.hasPreferentialProgram ? (
        <section
          className="customer-preferential-card"
          aria-labelledby="customer-preferential-title"
        >
          <div>
            <span className="eyebrow">Льготная программа</span>
            <h2 id="customer-preferential-title">
              Доступный бюджет по льготной ставке
            </h2>
          </div>
          <strong>
            {formatOptionalCurrency(
              customer.calculated.preferentialMaximumPropertyCost,
            )}
          </strong>
          <dl>
            <div>
              <dt>Ставка</dt>
              <dd>
                {formatPercent(customer.calculated.preferentialAnnualRate)}
              </dd>
            </div>
            <div>
              <dt>Лимит кредита</dt>
              <dd>
                {formatOptionalCurrency(
                  customer.calculated.preferentialCreditLimit,
                )}
              </dd>
            </div>
          </dl>
        </section>
      ) : null}

      <div className="customer-detail-sections">
        <section
          className="saved-property-card"
          aria-labelledby="customer-contacts-title"
        >
          <div className="section-heading">
            <div>
              <span className="eyebrow">Профиль</span>
              <h2 id="customer-contacts-title">Контакты и личные данные</h2>
            </div>
          </div>
          <dl className="property-detail-facts">
            <div><dt>Имя</dt><dd>{customer.firstName || '—'}</dd></div>
            <div><dt>Фамилия</dt><dd>{customer.lastName || '—'}</dd></div>
            <div>
              <dt>Телефон</dt>
              <dd>
                {customer.phone
                  ? <a href={`tel:${customer.phone}`}>{customer.phone}</a>
                  : '—'}
              </dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>
                {customer.email
                  ? <a href={`mailto:${customer.email}`}>{customer.email}</a>
                  : '—'}
              </dd>
            </div>
            <div><dt>Возраст</dt><dd>{customer.age ?? '—'}</dd></div>
            <div><dt>Дата или год рождения</dt><dd>{birthValue}</dd></div>
            <div>
              <dt>Город проживания</dt>
              <dd>{customer.residenceCity || '—'}</dd>
            </div>
            <div>
              <dt>Есть недвижимость</dt>
              <dd>{formatBoolean(customer.hasOwnedProperty)}</dd>
            </div>
          </dl>
        </section>

        <section
          className="saved-property-card"
          aria-labelledby="customer-budget-title"
        >
          <div className="section-heading">
            <div>
              <span className="eyebrow">Финансы</span>
              <h2 id="customer-budget-title">Бюджет и программы</h2>
            </div>
          </div>
          <dl className="property-detail-facts">
            <div>
              <dt>Первоначальный взнос</dt>
              <dd>{formatOptionalCurrency(customer.initialPaymentAmount)}</dd>
            </div>
            <div>
              <dt>Максимальный платёж</dt>
              <dd>{formatOptionalCurrency(customer.maximumMonthlyPayment)}</dd>
            </div>
            <div className="customer-fact--wide">
              <dt>Льготные программы</dt>
              <dd>
                {customer.preferentialPrograms.length > 0
                  ? customer.preferentialPrograms
                    .map((program) => program.name)
                    .join(', ')
                  : '—'}
              </dd>
            </div>
          </dl>
        </section>

        <section
          className="saved-property-card customer-preferences-card"
          aria-labelledby="customer-preferences-title"
        >
          <div className="section-heading">
            <div>
              <span className="eyebrow">Запрос</span>
              <h2 id="customer-preferences-title">Параметры недвижимости</h2>
            </div>
          </div>
          <dl className="property-detail-facts">
            <div>
              <dt>Цель покупки</dt>
              <dd>{customer.purchaseGoalLabel || '—'}</dd>
            </div>
            <div>
              <dt>Город</dt>
              <dd>{customer.desiredCity || '—'}</dd>
            </div>
            <div>
              <dt>Район</dt>
              <dd>{customer.desiredDistrict || '—'}</dd>
            </div>
            <div>
              <dt>Планировки</dt>
              <dd>
                {customer.desiredLayouts.length > 0
                  ? customer.desiredLayouts.map((layout) => layout.name).join(', ')
                  : '—'}
              </dd>
            </div>
            <div>
              <dt>Минимальная площадь</dt>
              <dd>{formatOptionalArea(customer.areaMinimum)}</dd>
            </div>
            <div>
              <dt>Максимальная площадь</dt>
              <dd>{formatOptionalArea(customer.areaMaximum)}</dd>
            </div>
            <div>
              <dt>Этаж</dt>
              <dd>{customer.desiredFloor || '—'}</dd>
            </div>
            <div>
              <dt>Стороны света</dt>
              <dd>{customer.cardinalDirections || '—'}</dd>
            </div>
            <div className="customer-fact--wide">
              <dt>Комментарий</dt>
              <dd>{customer.comment || '—'}</dd>
            </div>
          </dl>
        </section>
      </div>

      <section className="property-system-information" aria-label="Системная информация">
        <span>Создано: {formatDateTime(customer.createdAt)}</span>
        <span>Обновлено: {formatDateTime(customer.updatedAt)}</span>
      </section>

      <p className="legacy-fallback">
        Связанные расчёты, отчёты Word и операции изменения пока работают в{' '}
        <a className="text-link" href={customer.legacyDetailUrl}>
          Django-версии карточки
        </a>
        .
      </p>
    </div>
  )
}
