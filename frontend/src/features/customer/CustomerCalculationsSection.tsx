import { Notice } from '@/shared/ui/Notice'
import { restoreFocus } from '@/shared/lib/restoreFocus'
import { ModalDialog } from '@/shared/ui/ModalDialog'
import { SelectFilter } from '@/shared/ui/SelectFilter'
import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { Pagination } from '@/shared/ui/Pagination'
import { ResetFilters } from '@/shared/ui/ResetFilters'
import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { SortableHeader } from '@/shared/ui/SortableHeader'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useMemo, useRef, useState } from 'react'
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
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'
import { CalculationFilters } from '@/features/mortgage/CalculationFilters'
import { calculationFilterNames } from '@/features/mortgage/calculationFilterFields'
import { useTableParameters } from '@/shared/lib/useTableParameters'

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
    calculationFilterNames.forEach((name) => {
      const value = searchParameters.get(`calculation${name[0].toUpperCase()}${name.slice(1)}`)
      if (value) parameters.set(name, value)
    })
    parameters.set('pageSize', '10')
    return parameters
  }, [searchParameters])
  const tableParameters = useTableParameters(calculationParameters)
  const calculationsQuery = useQuery(
    customerCalculationListQueryOptions(
      customerIdentifier,
      tableParameters,
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
      window.setTimeout(() => restoreFocus(unlinkTriggerRef.current), 0)
    },
  })

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
    window.setTimeout(() => restoreFocus(unlinkTriggerRef.current), 0)
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
      <section className="saved-property-card detail-card" aria-labelledby="customer-calculations-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Ипотека</span>
            <h2 id="customer-calculations-title">Связанные расчёты</h2>
          </div>
        </div>
        <PageLoadingState compact title="Загружаем расчёты клиента…" className="status-notice" />
      </section>
    )
  }

  if (calculationsQuery.isError || !calculationsQuery.data) {
    return (
      <section className="saved-property-card detail-card" aria-labelledby="customer-calculations-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Ипотека</span>
            <h2 id="customer-calculations-title">Связанные расчёты</h2>
          </div>
        </div>
        <ErrorState
          title="Не удалось загрузить расчёты клиента"
          onRetry={() => calculationsQuery.refetch()}
        />
      </section>
    )
  }

  const { results, page, totalCount, totalPages } = calculationsQuery.data
  const selectedCount = selections.length
  const programType = searchParameters.get('calculationProgram') ?? 'all'

  return (
    <section className="saved-property-card customer-calculations detail-card" aria-labelledby="customer-calculations-title">
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
        <CalculationFilters prefix="calculation" />
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <div className="live-search-control">
            <LiveFilterInput label="Поиск по объекту" id="customer-calculation-search" parameter="calculationQ" placeholder="Город, ЖК, корпус или квартира" pageParameter="calculationPage" />
            <button className="button button--dark" type="submit">Найти</button>
          </div>
        </form>
        <SelectFilter label="Тип программы" parameter="calculationProgram" emptyLabel="Все расчёты"
          options={[{ value: 'market', label: 'Рыночные' }, { value: 'trench', label: 'Траншевые' }]} pageParameter="calculationPage" />
        <ResetFilters prefix="calculation" />
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
        <Notice as="p" tone="error" role="alert" className="form-error">
          Не удалось сформировать Word-отчёт. Повторите попытку.
        </Notice>
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
          <TableScrollArea className="table-card property-table-wrapper" label="Связанные расчёты клиента">
            <table className="property-table calculation-table customer-calculation-table">
              <caption className="visually-hidden">Связанные расчёты клиента</caption>
              <thead>
                <tr>
                  <th scope="col"><span className="visually-hidden">Выбор</span></th>
                  <SortableHeader field="createdAt" defaultOrdering="-createdAt" parameter="calculationOrdering" pageParameter="calculationPage">Дата</SortableHeader>
                  <SortableHeader field="programType" defaultOrdering="-createdAt" parameter="calculationOrdering" pageParameter="calculationPage">Тип</SortableHeader>
                  <SortableHeader field="realEstateComplex" defaultOrdering="-createdAt" parameter="calculationOrdering" pageParameter="calculationPage">Объект</SortableHeader>
                  <SortableHeader field="finalPropertyCost" defaultOrdering="-createdAt" parameter="calculationOrdering" pageParameter="calculationPage">Стоимость</SortableHeader>
                  <SortableHeader field="initialPaymentRubles" defaultOrdering="-createdAt" parameter="calculationOrdering" pageParameter="calculationPage">Первый взнос</SortableHeader>
                  <SortableHeader field="monthlyPayment" defaultOrdering="-createdAt" parameter="calculationOrdering" pageParameter="calculationPage">Платёж</SortableHeader>
                  <SortableHeader field="mortgageTermMonths" defaultOrdering="-createdAt" parameter="calculationOrdering" pageParameter="calculationPage">Срок</SortableHeader>
                  <SortableHeader field="annualRate" defaultOrdering="-createdAt" parameter="calculationOrdering" pageParameter="calculationPage">Ставка</SortableHeader>
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
                    <td>{formatCurrency(calculation.initialPaymentRubles)}</td>
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
          </TableScrollArea>
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
                  <div><dt>Первый взнос</dt><dd>{formatCurrency(calculation.initialPaymentRubles)}</dd></div>
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
        <Pagination label="Страницы расчётов клиента" page={page} totalPages={totalPages} onPageChange={(nextPage) => updateParameters({ calculationPage: String(nextPage) })} />
      ) : null}

      {calculationToUnlink ? (
        <ModalDialog labelledBy="unlink-calculation-title" describedBy="unlink-calculation-description" pending={unlinkMutation.isPending} onClose={closeUnlinkConfirmation}>
          <div>
            <h3 id="unlink-calculation-title">Отвязать расчёт от клиента?</h3>
            <p id="unlink-calculation-description">
              Расчёт останется в истории и его можно будет добавить снова.
            </p>
            {unlinkMutation.isError ? (
              <Notice as="p" tone="error" role="alert" className="form-error">
                Не удалось отвязать расчёт. Повторите попытку.
              </Notice>
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
        </ModalDialog>
      ) : null}
    </section>
  )
}
