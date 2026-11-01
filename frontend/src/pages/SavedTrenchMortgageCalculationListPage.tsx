import { LegacyLink } from '@/shared/ui/LegacyLink'
import { TableOrdering } from '@/shared/ui/TableOrdering'
import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { SortableHeader } from '@/shared/ui/SortableHeader'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import {
  linkCustomerCalculations,
  savedTrenchMortgageCalculationListQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type { SavedTrenchMortgageCalculationListItem } from '@/api/schemas'
import { CalculationFilters } from '@/features/mortgage/CalculationFilters'
import { useTableParameters } from '@/shared/lib/useTableParameters'
import {
  formatCurrency,
  formatDateTime,
  formatInteger,
  formatMonths,
  formatPercent,
} from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

function TrenchCalculationMobileCard({
  calculation,
  customerIdentifier,
  isSelected,
  onToggle,
}: {
  calculation: SavedTrenchMortgageCalculationListItem
  customerIdentifier: number | null
  isSelected: boolean
  onToggle: () => void
}) {
  return (
    <article className="property-mobile-card calculation-mobile-card">
      {customerIdentifier ? (
        <label className="calculation-selection">
          <input
            type="checkbox"
            checked={calculation.isLinked || isSelected}
            disabled={calculation.isLinked}
            onChange={onToggle}
          />
          {calculation.isLinked ? 'Уже добавлен клиенту' : 'Добавить клиенту'}
        </label>
      ) : null}
      <div className="property-mobile-card__heading">
        <div>
          <span>{calculation.property.city}</span>
          <h2>{calculation.property.realEstateComplex}</h2>
        </div>
        <strong>{formatCurrency(calculation.finalPropertyCost)}</strong>
      </div>
      <p className="calculation-mobile-card__date">
        Расчёт от {formatDateTime(calculation.createdAt)}
      </p>
      <dl>
        <div>
          <dt>Корпус / квартира</dt>
          <dd>
            {calculation.property.building} /{' '}
            {calculation.property.apartmentNumber}
          </dd>
        </div>
        <div>
          <dt>Максимальный платёж</dt>
          <dd>
            {calculation.maximumMonthlyPayment
              ? formatCurrency(calculation.maximumMonthlyPayment)
              : '—'}
          </dd>
        </div>
        <div>
          <dt>Последний платёж</dt>
          <dd>{calculation.lastMonthlyPayment ? formatCurrency(calculation.lastMonthlyPayment) : '—'}</dd>
        </div>
        <div>
          <dt>Срок</dt>
          <dd>{formatMonths(calculation.mortgageTermMonths)}</dd>
        </div>
        <div>
          <dt>Траншей</dt>
          <dd>{calculation.trenchCount}</dd>
        </div>
      </dl>
      <Link
        className="text-link"
        to={`/mortgage/trench/calculations/${calculation.id}`}
      >
        Открыть расчёт <span aria-hidden="true">→</span>
      </Link>
    </article>
  )
}

export function SavedTrenchMortgageCalculationListPage() {
  const [searchParameters, setSearchParameters] = useSearchParams()
  const tableParameters = useTableParameters(searchParameters)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const rawCustomerIdentifier = Number(searchParameters.get('customerId'))
  const customerIdentifier = Number.isInteger(rawCustomerIdentifier)
    && rawCustomerIdentifier > 0
    ? rawCustomerIdentifier
    : null
  const [selectedCalculationIdentifiers, setSelectedCalculationIdentifiers] =
    useState<Set<number>>(() => new Set())
  useDocumentTitle(
    customerIdentifier
      ? 'Добавление траншевых расчётов'
      : 'История траншевой ипотеки',
  )
  const sessionQuery = useQuery(sessionQueryOptions)
  const calculationQuery = useQuery({
    ...savedTrenchMortgageCalculationListQueryOptions(tableParameters),
    enabled: sessionQuery.data?.isAuthenticated === true,
  })
  const linkMutation = useMutation({
    mutationFn: () => linkCustomerCalculations(customerIdentifier ?? 0, {
      programType: 'trench',
      calculationIds: Array.from(selectedCalculationIdentifiers),
    }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['customer-calculations', customerIdentifier],
      })
      navigate(`/customers/${customerIdentifier}`)
    },
  })

  const toggleCalculation = (calculationIdentifier: number) => {
    setSelectedCalculationIdentifiers((currentIdentifiers) => {
      const nextIdentifiers = new Set(currentIdentifiers)
      if (nextIdentifiers.has(calculationIdentifier)) {
        nextIdentifiers.delete(calculationIdentifier)
      } else {
        nextIdentifiers.add(calculationIdentifier)
      }
      return nextIdentifiers
    })
  }

  const updateParameters = (updates: Record<string, string | null>) => {
    const nextParameters = new URLSearchParams(searchParameters)
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) nextParameters.delete(key)
      else nextParameters.set(key, value)
    })
    setSearchParameters(nextParameters)
  }

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const searchInput = event.currentTarget.elements.namedItem('q')
    const searchValue = searchInput instanceof HTMLInputElement
      ? searchInput.value.trim()
      : ''
    updateParameters({ q: searchValue || null, page: null })
  }

  if (sessionQuery.isLoading) return <PageLoadingState />

  if (!sessionQuery.data?.isAuthenticated) {
    return (
      <div className="page-stack">
        <header className="page-header">
          <div>
            <span className="eyebrow">Личный раздел</span>
            <h1>История траншевой ипотеки</h1>
          </div>
        </header>
        <EmptyState
          title="Войдите, чтобы открыть историю"
          description="Сохранённые траншевые расчёты доступны только владельцу аккаунта."
          action={(
            <a
              className="button button--primary"
              href={`/app/login?next=${encodeURIComponent(
                '/app/mortgage/trench/calculations',
              )}`}
            >
              Войти
            </a>
          )}
        />
      </div>
    )
  }

  if (calculationQuery.isLoading) return <PageLoadingState />
  if (calculationQuery.isError || !calculationQuery.data) {
    return <ErrorState onRetry={() => void calculationQuery.refetch()} />
  }

  const { results, page, totalCount, totalPages } = calculationQuery.data


  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Личный раздел</span>
          <h1>{customerIdentifier ? 'Добавление траншевых расчётов' : 'История траншевой ипотеки'}</h1>
          <p>
            {customerIdentifier
              ? 'Выберите сохранённые траншевые сценарии для карточки клиента.'
              : 'Сохранённые сценарии поэтапного финансирования с повторным расчётом и выгрузкой отчётов.'}
          </p>
        </div>
        <div className="page-header__actions">
          {customerIdentifier ? (
            <Link className="button button--secondary" to={`/customers/${customerIdentifier}`}>
              К клиенту
            </Link>
          ) : (
            <LegacyLink
              className="button button--secondary"
              href="/mortgage/trench-calculations/"
            >
              Прежняя версия
            </LegacyLink>
          )}
          <Link className="button button--primary" to="/mortgage/trench">
            Новый расчёт
          </Link>
        </div>
      </header>

      <section className="filter-panel" aria-label="Фильтры траншевой истории">
        <CalculationFilters />
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <div className="live-search-control">
            <LiveFilterInput label="Поиск по объекту" id="trench-calculation-search" parameter="q" placeholder="Город, ЖК, корпус или квартира" />
            <button className="button button--dark" type="submit">Найти</button>
          </div>
        </form>
        <TableOrdering id="trench-calculation-ordering" defaultOrdering="-createdAt" parameter="ordering" pageParameter="page"
          fields={[{ field: 'createdAt', label: "Дата" }, { field: 'city', label: "Город" }, { field: 'realEstateComplex', label: "Объект" }, { field: 'finalPropertyCost', label: "Стоимость" }, { field: 'initialPaymentRubles', label: "Первый взнос" }, { field: 'maximumMonthlyPayment', label: "Макс. платёж" }, { field: 'monthlyPayment', label: "Последний платёж" }, { field: 'mortgageTermMonths', label: "Срок" }, { field: 'annualRate', label: "Ставка / транши" }]} />
      </section>

      <div className="results-heading" aria-live="polite">
        <p>
          Сохранено расчётов: <strong>{formatInteger(totalCount)}</strong>
        </p>
        {customerIdentifier ? (
          <div>
            <span>Выбрано: {selectedCalculationIdentifiers.size}</span>
            <button
              className="button button--primary"
              type="button"
              disabled={selectedCalculationIdentifiers.size === 0 || linkMutation.isPending}
              onClick={() => linkMutation.mutate()}
            >
              {linkMutation.isPending ? 'Добавляем…' : 'Добавить клиенту'}
            </button>
          </div>
        ) : calculationQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>
      {linkMutation.isError ? (
        <p className="form-error" role="alert">
          Не удалось добавить расчёты клиенту. Повторите попытку.
        </p>
      ) : null}

      {results.length === 0 ? (
        <EmptyState
          title="Сохранённых расчётов пока нет"
          description={searchParameters.get('q')
            ? 'По вашему запросу ничего не найдено.'
            : 'Выберите объект, рассчитайте траншевую ипотеку и сохраните результат.'}
          action={searchParameters.get('q') ? (
            <button
              className="button button--secondary"
              type="button"
              onClick={() => setSearchParameters(
                customerIdentifier ? { customerId: String(customerIdentifier) } : {},
              )}
            >
              Сбросить фильтры
            </button>
          ) : (
            <Link className="button button--primary" to="/properties">
              Выбрать объект
            </Link>
          )}
        />
      ) : (
        <>
          <div className="table-card property-table-wrapper">
            <table className="property-table calculation-table">
              <caption className="visually-hidden">
                История траншевых ипотечных расчётов
              </caption>
              <thead>
                <tr>
                  {customerIdentifier ? <th scope="col"><span className="visually-hidden">Выбор</span></th> : null}
                  <SortableHeader field="createdAt" defaultOrdering="-createdAt">Дата</SortableHeader>
                  <SortableHeader field="city" defaultOrdering="-createdAt">Город</SortableHeader>
                  <SortableHeader field="realEstateComplex" defaultOrdering="-createdAt">Объект</SortableHeader>
                  <SortableHeader field="finalPropertyCost" defaultOrdering="-createdAt">Стоимость</SortableHeader>
                  <SortableHeader field="initialPaymentRubles" defaultOrdering="-createdAt">Первый взнос</SortableHeader>
                  <SortableHeader field="maximumMonthlyPayment" defaultOrdering="-createdAt">Макс. платёж</SortableHeader>
                  <SortableHeader field="monthlyPayment" defaultOrdering="-createdAt">Последний платёж</SortableHeader>
                  <SortableHeader field="mortgageTermMonths" defaultOrdering="-createdAt">Срок</SortableHeader>
                  <SortableHeader field="annualRate" defaultOrdering="-createdAt">Ставка / транши</SortableHeader>
                  <th scope="col">
                    <span className="visually-hidden">Действия</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {results.map((calculation) => (
                  <tr key={calculation.id}>
                    {customerIdentifier ? (
                      <td>
                        <input
                          type="checkbox"
                          checked={calculation.isLinked || selectedCalculationIdentifiers.has(calculation.id)}
                          disabled={calculation.isLinked}
                          onChange={() => toggleCalculation(calculation.id)}
                          aria-label={calculation.isLinked
                            ? `Расчёт от ${formatDateTime(calculation.createdAt)} уже добавлен клиенту`
                            : `Добавить расчёт от ${formatDateTime(calculation.createdAt)} клиенту`}
                        />
                      </td>
                    ) : null}
                    <td>{formatDateTime(calculation.createdAt)}</td>
                    <td>{calculation.property.city}</td>
                    <td>
                      <strong>{calculation.property.realEstateComplex}</strong>
                      <small>
                        корп. {calculation.property.building}, кв.{' '}
                        {calculation.property.apartmentNumber}
                      </small>
                    </td>
                    <td>{formatCurrency(calculation.finalPropertyCost)}</td>
                    <td>{formatCurrency(calculation.initialPaymentRubles)}</td>
                    <td>
                      <strong>
                        {calculation.maximumMonthlyPayment
                          ? formatCurrency(calculation.maximumMonthlyPayment)
                          : '—'}
                      </strong>
                    </td>
                    <td>{calculation.lastMonthlyPayment ? formatCurrency(calculation.lastMonthlyPayment) : '—'}</td>
                    <td>{formatMonths(calculation.mortgageTermMonths)}</td>
                    <td>
                      {formatPercent(calculation.annualRate)}
                      <small>{calculation.trenchCount} транша</small>
                    </td>
                    <td>
                      <Link
                        className="row-action"
                        to={`/mortgage/trench/calculations/${calculation.id}`}
                        aria-label={`Открыть расчёт от ${formatDateTime(
                          calculation.createdAt,
                        )}`}
                      >
                        →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="property-mobile-list">
            {results.map((calculation) => (
              <TrenchCalculationMobileCard
                calculation={calculation}
                customerIdentifier={customerIdentifier}
                isSelected={selectedCalculationIdentifiers.has(calculation.id)}
                onToggle={() => toggleCalculation(calculation.id)}
                key={calculation.id}
              />
            ))}
          </div>
        </>
      )}

      {totalPages > 1 ? (
        <nav className="pagination" aria-label="Страницы траншевой истории">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => updateParameters({ page: String(page - 1) })}
          >
            <span aria-hidden="true">←</span> Назад
          </button>
          <span>
            Страница <strong>{page}</strong> из {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => updateParameters({ page: String(page + 1) })}
          >
            Далее <span aria-hidden="true">→</span>
          </button>
        </nav>
      ) : null}
    </div>
  )
}
