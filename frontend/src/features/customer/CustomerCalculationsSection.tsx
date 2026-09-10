import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import {
  customerCalculationListQueryOptions,
  exportCustomerCalculationsWord,
  unlinkCustomerCalculation,
} from '@/api/queries'
import type {
  CustomerCalculationListItem,
  CustomerCalculationSelection,
} from '@/api/schemas'
import {
  formatCurrency,
  formatDateTime,
  formatInteger,
  formatMonths,
  formatPercent,
} from '@/shared/lib/formatters'
import { EmptyState, ErrorState } from '@/shared/ui/AsyncState'

const orderingOptions = [
  { value: '-createdAt', label: 'Сначала новые' },
  { value: 'createdAt', label: 'Сначала старые' },
  { value: 'finalPropertyCost', label: 'Стоимость: по возрастанию' },
  { value: '-finalPropertyCost', label: 'Стоимость: по убыванию' },
  { value: 'monthlyPayment', label: 'Платёж: по возрастанию' },
  { value: '-monthlyPayment', label: 'Платёж: по убыванию' },
  { value: 'annualRate', label: 'Ставка: по возрастанию' },
  { value: '-annualRate', label: 'Ставка: по убыванию' },
]

function calculationToken(calculation: CustomerCalculationSelection) {
  return `${calculation.programType}:${calculation.linkId}`
}

function calculationDetailPath(calculation: CustomerCalculationListItem) {
  return calculation.programType === 'trench'
    ? `/mortgage/trench/calculations/${calculation.calculationId}`
    : `/mortgage/calculations/${calculation.calculationId}`
}

function downloadFile(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}

type CustomerCalculationsSectionProps = {
  customerIdentifier: number
  customerName: string
}

export function CustomerCalculationsSection({
  customerIdentifier,
  customerName,
}: CustomerCalculationsSectionProps) {
  const queryClient = useQueryClient()
  const [searchParameters, setSearchParameters] = useSearchParams()
  const [selections, setSelections] = useState<CustomerCalculationSelection[]>([])
  const [calculationToUnlink, setCalculationToUnlink] =
    useState<CustomerCalculationListItem | null>(null)
  const unlinkTriggerRef = useRef<HTMLButtonElement | null>(null)
  const unlinkConfirmRef = useRef<HTMLButtonElement>(null)
  const calculationParameters = useMemo(() => {
    const parameters = new URLSearchParams()
    const query = searchParameters.get('calculationQ')
    const programType = searchParameters.get('calculationProgram')
    const ordering = searchParameters.get('calculationOrdering')
    const page = searchParameters.get('calculationPage')
    if (query) parameters.set('q', query)
    if (programType) parameters.set('programType', programType)
    if (ordering) parameters.set('ordering', ordering)
    if (page) parameters.set('page', page)
    parameters.set('pageSize', '10')
    return parameters
  }, [searchParameters])
  const calculationsQuery = useQuery(
    customerCalculationListQueryOptions(
      customerIdentifier,
      calculationParameters,
    ),
  )
  const exportMutation = useMutation({
    mutationFn: () => exportCustomerCalculationsWord(
      customerIdentifier,
      selections,
    ),
    onSuccess: ({ blob, filename }) => downloadFile(blob, filename),
  })
  const unlinkMutation = useMutation({
    mutationFn: (calculation: CustomerCalculationListItem) =>
      unlinkCustomerCalculation(
        customerIdentifier,
        calculation.programType,
        calculation.linkId,
      ),
    onSuccess: async (_, calculation) => {
      setSelections((currentSelections) => currentSelections.filter(
        (selection) => calculationToken(selection) !== calculationToken({
          programType: calculation.programType,
          linkId: calculation.linkId,
        }),
      ))
      setCalculationToUnlink(null)
      await queryClient.invalidateQueries({
        queryKey: ['customer-calculations', customerIdentifier],
      })
      window.setTimeout(() => unlinkTriggerRef.current?.focus(), 0)
    },
  })

  useEffect(() => {
    if (!calculationToUnlink) return
    unlinkConfirmRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setCalculationToUnlink(null)
      unlinkMutation.reset()
      window.setTimeout(() => unlinkTriggerRef.current?.focus(), 0)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [calculationToUnlink, unlinkMutation])

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
    const searchInput = event.currentTarget.elements.namedItem('calculationQ')
    const searchValue = searchInput instanceof HTMLInputElement
      ? searchInput.value.trim()
      : ''
    updateParameters({
      calculationQ: searchValue || null,
      calculationPage: null,
    })
  }

  const toggleSelection = (calculation: CustomerCalculationListItem) => {
    const selection = {
      programType: calculation.programType,
      linkId: calculation.linkId,
    }
    const token = calculationToken(selection)
    setSelections((currentSelections) => {
      const alreadySelected = currentSelections.some(
        (currentSelection) => calculationToken(currentSelection) === token,
      )
      return alreadySelected
        ? currentSelections.filter(
          (currentSelection) => calculationToken(currentSelection) !== token,
        )
        : [...currentSelections, selection]
    })
  }

  const closeUnlinkConfirmation = () => {
    setCalculationToUnlink(null)
    unlinkMutation.reset()
    window.setTimeout(() => unlinkTriggerRef.current?.focus(), 0)
  }

  const openUnlinkConfirmation = (
    calculation: CustomerCalculationListItem,
    trigger: HTMLButtonElement,
  ) => {
    unlinkTriggerRef.current = trigger
    setCalculationToUnlink(calculation)
  }

  const isSelected = (calculation: CustomerCalculationListItem) =>
    selections.some((selection) => calculationToken(selection)
      === calculationToken({
        programType: calculation.programType,
        linkId: calculation.linkId,
      }))

  if (calculationsQuery.isLoading) {
    return (
      <section className="saved-property-card" aria-labelledby="customer-calculations-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Ипотека</span>
            <h2 id="customer-calculations-title">Связанные расчёты</h2>
          </div>
        </div>
        <p className="status-notice" role="status">Загружаем расчёты клиента…</p>
      </section>
    )
  }

  if (calculationsQuery.isError || !calculationsQuery.data) {
    return (
      <section className="saved-property-card" aria-labelledby="customer-calculations-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Ипотека</span>
            <h2 id="customer-calculations-title">Связанные расчёты</h2>
          </div>
        </div>
        <ErrorState
          title="Не удалось загрузить расчёты клиента"
          onRetry={() => void calculationsQuery.refetch()}
        />
      </section>
    )
  }

  const { results, page, totalCount, totalPages } = calculationsQuery.data
  const selectedCount = selections.length
  const programType = searchParameters.get('calculationProgram') ?? 'all'
  const ordering = searchParameters.get('calculationOrdering') ?? '-createdAt'

  return (
    <section className="saved-property-card customer-calculations" aria-labelledby="customer-calculations-title">
      <div className="section-heading section-heading--with-action">
        <div>
          <span className="eyebrow">Ипотека</span>
          <h2 id="customer-calculations-title">Связанные расчёты</h2>
          <p>Рыночные и траншевые сценарии для {customerName}.</p>
        </div>
        <div className="page-header__actions">
          <Link
            className="button button--secondary"
            to={`/mortgage/calculations?customerId=${customerIdentifier}`}
          >
            Добавить рыночный
          </Link>
          <Link
            className="button button--secondary"
            to={`/mortgage/trench/calculations?customerId=${customerIdentifier}`}
          >
            Добавить траншевый
          </Link>
          <Link
            className="button button--primary"
            to={`/properties?customerId=${customerIdentifier}`}
          >
            Новый расчёт
          </Link>
        </div>
      </div>

      <div className="customer-calculation-toolbar">
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <label htmlFor="customer-calculation-search">Поиск по объекту</label>
          <div className="search-control">
            <span aria-hidden="true">⌕</span>
            <input
              id="customer-calculation-search"
              name="calculationQ"
              type="search"
              key={searchParameters.get('calculationQ') ?? ''}
              defaultValue={searchParameters.get('calculationQ') ?? ''}
              placeholder="Город, ЖК, корпус или квартира"
            />
            <button className="button button--dark" type="submit">Найти</button>
          </div>
        </form>
        <div className="sort-control">
          <label htmlFor="customer-calculation-program">Тип программы</label>
          <select
            id="customer-calculation-program"
            value={programType}
            onChange={(event) => updateParameters({
              calculationProgram: event.target.value === 'all'
                ? null
                : event.target.value,
              calculationPage: null,
            })}
          >
            <option value="all">Все расчёты</option>
            <option value="market">Рыночные</option>
            <option value="trench">Траншевые</option>
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="customer-calculation-ordering">Сортировка</label>
          <select
            id="customer-calculation-ordering"
            value={ordering}
            onChange={(event) => updateParameters({
              calculationOrdering: event.target.value,
              calculationPage: null,
            })}
          >
            {orderingOptions.map((option) => (
              <option value={option.value} key={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="results-heading customer-calculation-results">
        <p>Расчётов: <strong>{formatInteger(totalCount)}</strong></p>
        <div>
          <span aria-live="polite">Выбрано: {selectedCount}</span>
          <button
            className="button button--secondary"
            type="button"
            disabled={selectedCount === 0 || exportMutation.isPending}
            onClick={() => exportMutation.mutate()}
          >
            {exportMutation.isPending ? 'Формируем…' : 'Скачать Word'}
          </button>
        </div>
      </div>
      {exportMutation.isError ? (
        <p className="form-error" role="alert">
          Не удалось сформировать Word-отчёт. Повторите попытку.
        </p>
      ) : null}

      {results.length === 0 ? (
        <EmptyState
          title="Связанных расчётов пока нет"
          description={searchParameters.get('calculationQ') || programType !== 'all'
            ? 'По выбранным фильтрам ничего не найдено.'
            : 'Создайте новый расчёт или добавьте сохранённый из истории.'}
        />
      ) : (
        <>
          <div className="table-card property-table-wrapper">
            <table className="property-table calculation-table customer-calculation-table">
              <caption className="visually-hidden">Связанные расчёты клиента</caption>
              <thead>
                <tr>
                  <th scope="col"><span className="visually-hidden">Выбор</span></th>
                  <th scope="col">Дата</th>
                  <th scope="col">Тип</th>
                  <th scope="col">Объект</th>
                  <th scope="col">Стоимость</th>
                  <th scope="col">Платёж</th>
                  <th scope="col">Срок</th>
                  <th scope="col">Ставка</th>
                  <th scope="col"><span className="visually-hidden">Действия</span></th>
                </tr>
              </thead>
              <tbody>
                {results.map((calculation) => (
                  <tr key={calculationToken(calculation)}>
                    <td>
                      <input
                        type="checkbox"
                        checked={isSelected(calculation)}
                        onChange={() => toggleSelection(calculation)}
                        aria-label={`Выбрать расчёт от ${formatDateTime(calculation.createdAt)}`}
                      />
                    </td>
                    <td>{formatDateTime(calculation.createdAt)}</td>
                    <td>{calculation.programType === 'trench' ? 'Траншевая' : 'Рыночная'}</td>
                    <td>
                      <strong>{calculation.property.realEstateComplex}</strong>
                      <small>
                        {calculation.property.city}, корп. {calculation.property.building}, кв. {calculation.property.apartmentNumber}
                      </small>
                    </td>
                    <td>{formatCurrency(calculation.finalPropertyCost)}</td>
                    <td>{calculation.monthlyPayment ? formatCurrency(calculation.monthlyPayment) : '—'}</td>
                    <td>{formatMonths(calculation.mortgageTermMonths)}</td>
                    <td>{formatPercent(calculation.annualRate)}</td>
                    <td>
                      <div className="customer-calculation-actions">
                        <Link className="row-action" to={calculationDetailPath(calculation)}>
                          <span className="visually-hidden">Открыть расчёт</span>→
                        </Link>
                        <button
                          className="row-action row-action--button"
                          type="button"
                          aria-label={`Отвязать расчёт от ${formatDateTime(calculation.createdAt)}`}
                          onClick={(event) => openUnlinkConfirmation(
                            calculation,
                            event.currentTarget,
                          )}
                        >
                          ×
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="property-mobile-list">
            {results.map((calculation) => (
              <article
                className="property-mobile-card calculation-mobile-card"
                key={calculationToken(calculation)}
              >
                <label className="calculation-selection">
                  <input
                    type="checkbox"
                    checked={isSelected(calculation)}
                    onChange={() => toggleSelection(calculation)}
                  />
                  Выбрать для отчёта
                </label>
                <div className="property-mobile-card__heading">
                  <div>
                    <span>{calculation.programType === 'trench' ? 'Траншевая' : 'Рыночная'}</span>
                    <h3>{calculation.property.realEstateComplex}</h3>
                  </div>
                  <strong>{formatCurrency(calculation.finalPropertyCost)}</strong>
                </div>
                <p>Расчёт от {formatDateTime(calculation.createdAt)}</p>
                <dl>
                  <div><dt>Объект</dt><dd>{calculation.property.city}, корп. {calculation.property.building}, кв. {calculation.property.apartmentNumber}</dd></div>
                  <div><dt>Платёж</dt><dd>{calculation.monthlyPayment ? formatCurrency(calculation.monthlyPayment) : '—'}</dd></div>
                  <div><dt>Срок</dt><dd>{formatMonths(calculation.mortgageTermMonths)}</dd></div>
                  <div><dt>Ставка</dt><dd>{formatPercent(calculation.annualRate)}</dd></div>
                </dl>
                <div className="customer-calculation-actions">
                  <Link className="text-link" to={calculationDetailPath(calculation)}>
                    Открыть расчёт <span aria-hidden="true">→</span>
                  </Link>
                  <button
                    className="text-button text-button--danger"
                    type="button"
                    onClick={(event) => openUnlinkConfirmation(
                      calculation,
                      event.currentTarget,
                    )}
                  >
                    Отвязать
                  </button>
                </div>
              </article>
            ))}
          </div>
        </>
      )}

      {totalPages > 1 ? (
        <nav className="pagination" aria-label="Страницы расчётов клиента">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => updateParameters({ calculationPage: String(page - 1) })}
          >
            <span aria-hidden="true">←</span> Назад
          </button>
          <span>Страница <strong>{page}</strong> из {totalPages}</span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => updateParameters({ calculationPage: String(page + 1) })}
          >
            Далее <span aria-hidden="true">→</span>
          </button>
        </nav>
      ) : null}

      {calculationToUnlink ? (
        <div
          className="delete-confirmation"
          role="alertdialog"
          aria-labelledby="unlink-calculation-title"
          aria-describedby="unlink-calculation-description"
        >
          <div>
            <h3 id="unlink-calculation-title">Отвязать расчёт от клиента?</h3>
            <p id="unlink-calculation-description">
              Расчёт останется в истории и его можно будет добавить снова.
            </p>
            {unlinkMutation.isError ? (
              <p className="form-error" role="alert">
                Не удалось отвязать расчёт. Повторите попытку.
              </p>
            ) : null}
          </div>
          <div className="delete-confirmation__actions">
            <button
              className="button button--secondary"
              type="button"
              disabled={unlinkMutation.isPending}
              onClick={closeUnlinkConfirmation}
            >
              Отмена
            </button>
            <button
              className="button button--danger"
              type="button"
              ref={unlinkConfirmRef}
              disabled={unlinkMutation.isPending}
              onClick={() => unlinkMutation.mutate(calculationToUnlink)}
            >
              {unlinkMutation.isPending ? 'Отвязываем…' : 'Отвязать расчёт'}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  )
}
