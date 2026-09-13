import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  calculateTrenchMortgage,
  mortgageOptionsQueryOptions,
  saveTrenchMortgageCalculation,
  savedTrenchMortgageCalculationDetailQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type {
  TrenchMortgageCalculationRequest,
  TrenchMortgageEntryRequest,
} from '@/api/schemas'
import { TrenchMortgageResult } from '@/features/mortgage/TrenchMortgageResult'
import { formatMonths, formatPercent } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'

type TrenchRowState = {
  date: string
  amountUnit: 'percent' | 'rubles'
  amountValue: string
  annualRate: string
}

type TrenchMortgageFormState = {
  propertyCost: string
  priceAdjustmentType: 'discount' | 'markup'
  priceAdjustmentUnit: 'percent' | 'rubles'
  priceAdjustmentValue: string
  initialPaymentUnit: 'percent' | 'rubles'
  initialPaymentValue: string
  initialPaymentDate: string
  mortgageTermMonths: string
  annualRate: string
  bankId: string
  bankProgramId: string
  trenchCount: number
  trenches: TrenchRowState[]
}

type FieldErrors = Record<string, string>

function getLocalDateInputValue() {
  const currentDate = new Date()
  const timezoneOffset = currentDate.getTimezoneOffset() * 60_000
  return new Date(currentDate.getTime() - timezoneOffset)
    .toISOString()
    .slice(0, 10)
}

function buildInitialTrenches(
  initialPaymentDate: string,
  annualRate: string,
): TrenchRowState[] {
  return Array.from({ length: 5 }, (_, index) => ({
    date: index === 0 ? initialPaymentDate : '',
    amountUnit: 'percent',
    amountValue: index === 0 ? '50' : '',
    annualRate,
  }))
}

function collectFieldErrors(
  value: unknown,
  prefix = '',
  result: FieldErrors = {},
): FieldErrors {
  if (typeof value === 'string' && prefix) {
    result[prefix] ??= value
    return result
  }
  if (Array.isArray(value)) {
    if (typeof value[0] === 'string' && prefix) {
      result[prefix] ??= value[0]
      return result
    }
    value.forEach((item, index) => {
      collectFieldErrors(item, prefix ? `${prefix}.${index}` : `${index}`, result)
    })
    return result
  }
  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([key, nestedValue]) => {
      collectFieldErrors(
        nestedValue,
        prefix ? `${prefix}.${key}` : key,
        result,
      )
    })
  }
  return result
}

function extractFieldErrors(error: unknown): FieldErrors {
  if (!(error instanceof ApiError) || !error.details) return {}
  return collectFieldErrors(error.details)
}

function FieldError({
  fieldName,
  errors,
}: {
  fieldName: string
  errors: FieldErrors
}) {
  const message = errors[fieldName]
  if (!message) return null
  return <span className="field-error" id={`${fieldName}-error`}>{message}</span>
}

function buildPayload(
  formState: TrenchMortgageFormState,
): TrenchMortgageCalculationRequest {
  const trenches: TrenchMortgageEntryRequest[] = formState.trenches
    .slice(0, formState.trenchCount)
    .map((trench, index) => ({
      date: trench.date,
      amountUnit: trench.amountUnit,
      amountValue: index === formState.trenchCount - 1
        ? null
        : trench.amountValue,
      annualRate: trench.annualRate,
    }))
  return {
    propertyCost: formState.propertyCost,
    priceAdjustmentType: formState.priceAdjustmentType,
    priceAdjustmentUnit: formState.priceAdjustmentUnit,
    priceAdjustmentValue: formState.priceAdjustmentValue,
    initialPaymentUnit: formState.initialPaymentUnit,
    initialPaymentValue: formState.initialPaymentValue,
    initialPaymentDate: formState.initialPaymentDate,
    mortgageTermMonths: Number(formState.mortgageTermMonths),
    annualRate: formState.annualRate,
    trenches,
  }
}

export function TrenchMortgageCalculatorPage() {
  useDocumentTitle('Траншевая ипотека')
  const [searchParameters] = useSearchParams()
  const queryClient = useQueryClient()
  const optionsQuery = useQuery(mortgageOptionsQueryOptions)
  const sessionQuery = useQuery(sessionQueryOptions)
  const resultHeadingRef = useRef<HTMLHeadingElement>(null)
  const appliedSampleIdentifierRef = useRef<number | null>(null)
  const initialPaymentDate = getLocalDateInputValue()
  const rawPropertyIdentifier = Number(searchParameters.get('propertyId'))
  const directPropertyIdentifier = Number.isInteger(rawPropertyIdentifier)
    && rawPropertyIdentifier > 0
    ? rawPropertyIdentifier
    : null
  const rawCustomerIdentifier = Number(searchParameters.get('customerId'))
  const customerIdentifier = Number.isInteger(rawCustomerIdentifier)
    && rawCustomerIdentifier > 0
    ? rawCustomerIdentifier
    : null
  const rawSampleIdentifier = Number(searchParameters.get('sample'))
  const sampleIdentifier = Number.isInteger(rawSampleIdentifier)
    && rawSampleIdentifier > 0
    ? rawSampleIdentifier
    : null
  const sampleQuery = useQuery({
    ...savedTrenchMortgageCalculationDetailQueryOptions(
      sampleIdentifier ?? 0,
    ),
    enabled: sessionQuery.data?.isAuthenticated === true
      && sampleIdentifier !== null,
  })
  const calculationQueryString = searchParameters.toString()
  const marketCalculatorPath = `/mortgage${
    calculationQueryString ? `?${calculationQueryString}` : ''
  }`
  const loginReturnPath = `/app/mortgage/trench${
    calculationQueryString ? `?${calculationQueryString}` : ''
  }`
  const [formState, setFormState] = useState<TrenchMortgageFormState>(() => {
    const annualRate = '15'
    return {
      propertyCost: searchParameters.get('propertyCost') ?? '5000000',
      priceAdjustmentType: 'discount',
      priceAdjustmentUnit: 'percent',
      priceAdjustmentValue: '0',
      initialPaymentUnit: 'percent',
      initialPaymentValue: '20',
      initialPaymentDate,
      mortgageTermMonths: '360',
      annualRate,
      bankId: '',
      bankProgramId: '',
      trenchCount: 2,
      trenches: buildInitialTrenches(initialPaymentDate, annualRate),
    }
  })
  const calculationMutation = useMutation({
    mutationFn: calculateTrenchMortgage,
  })
  const saveMutation = useMutation({
    mutationFn: saveTrenchMortgageCalculation,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['saved-trench-mortgage-calculations'],
      })
      if (customerIdentifier) {
        await queryClient.invalidateQueries({
          queryKey: ['customer-calculations', customerIdentifier],
        })
      }
    },
  })
  const propertyIdentifier = directPropertyIdentifier
    ?? sampleQuery.data?.property.id
    ?? null
  const fieldErrors = extractFieldErrors(calculationMutation.error)
  const availablePrograms = useMemo(
    () => optionsQuery.data?.programs.filter(
      (program) => String(program.bankId) === formState.bankId,
    ) ?? [],
    [formState.bankId, optionsQuery.data],
  )

  useEffect(() => {
    if (calculationMutation.isSuccess) {
      resultHeadingRef.current?.focus({ preventScroll: true })
      resultHeadingRef.current?.scrollIntoView?.({ block: 'start' })
    }
  }, [calculationMutation.isSuccess, calculationMutation.data])

  useEffect(() => {
    if (
      !sampleQuery.data
      || appliedSampleIdentifierRef.current === sampleQuery.data.id
    ) {
      return
    }
    const assumptions = sampleQuery.data.calculation.assumptions
    const savedTrenches = sampleQuery.data.calculation.trenches
    const initialTrenches = buildInitialTrenches(
      assumptions.initialPaymentDate,
      assumptions.annualRate,
    )
    setFormState({
      propertyCost: assumptions.basePropertyCost,
      priceAdjustmentType: assumptions.priceAdjustmentType,
      priceAdjustmentUnit: 'percent',
      priceAdjustmentValue: assumptions.priceAdjustmentPercent,
      initialPaymentUnit: 'percent',
      initialPaymentValue: assumptions.initialPaymentPercent,
      initialPaymentDate: assumptions.initialPaymentDate,
      mortgageTermMonths: String(assumptions.mortgageTermMonths),
      annualRate: assumptions.annualRate,
      bankId: '',
      bankProgramId: '',
      trenchCount: savedTrenches.length,
      trenches: initialTrenches.map((trench, index) => {
        const savedTrench = savedTrenches[index]
        if (!savedTrench) return trench
        return {
          date: savedTrench.date,
          amountUnit: 'percent',
          amountValue: index === savedTrenches.length - 1
            ? ''
            : savedTrench.percent,
          annualRate: savedTrench.annualRate,
        }
      }),
    })
    appliedSampleIdentifierRef.current = sampleQuery.data.id
  }, [sampleQuery.data])

  const updateField = <FieldName extends keyof TrenchMortgageFormState>(
    fieldName: FieldName,
    value: TrenchMortgageFormState[FieldName],
  ) => {
    if (calculationMutation.isError) calculationMutation.reset()
    setFormState((current) => ({ ...current, [fieldName]: value }))
  }

  const updateInitialPaymentDate = (value: string) => {
    if (calculationMutation.isError) calculationMutation.reset()
    setFormState((current) => ({
      ...current,
      initialPaymentDate: value,
      trenches: current.trenches.map((trench, index) => (
        index === 0
        && (!trench.date || trench.date === current.initialPaymentDate)
          ? { ...trench, date: value }
          : trench
      )),
    }))
  }

  const updateAnnualRate = (value: string) => {
    if (calculationMutation.isError) calculationMutation.reset()
    setFormState((current) => ({
      ...current,
      annualRate: value,
      trenches: current.trenches.map((trench) => (
        !trench.annualRate || trench.annualRate === current.annualRate
          ? { ...trench, annualRate: value }
          : trench
      )),
    }))
  }

  const updateTrench = <FieldName extends keyof TrenchRowState>(
    trenchIndex: number,
    fieldName: FieldName,
    value: TrenchRowState[FieldName],
  ) => {
    if (calculationMutation.isError) calculationMutation.reset()
    setFormState((current) => ({
      ...current,
      trenches: current.trenches.map((trench, index) => (
        index === trenchIndex
          ? { ...trench, [fieldName]: value }
          : trench
      )),
    }))
  }

  const selectProgram = (programIdentifier: string) => {
    const program = optionsQuery.data?.programs.find(
      (item) => String(item.id) === programIdentifier,
    )
    if (!program) {
      updateField('bankProgramId', '')
      return
    }
    setFormState((current) => {
      const maximumTermMonths = program.maximumLoanTermYears
        ? program.maximumLoanTermYears * 12
        : Number(current.mortgageTermMonths)
      const minimumInitialPayment = Number(program.minimumInitialPaymentPercent)
      return {
        ...current,
        bankProgramId: programIdentifier,
        annualRate: program.interestRate,
        mortgageTermMonths: String(
          Math.min(Number(current.mortgageTermMonths), maximumTermMonths),
        ),
        initialPaymentValue: current.initialPaymentUnit === 'percent'
          ? String(Math.max(Number(current.initialPaymentValue), minimumInitialPayment))
          : current.initialPaymentValue,
        trenches: current.trenches.map((trench) => ({
          ...trench,
          annualRate: program.interestRate,
        })),
      }
    })
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    saveMutation.reset()
    calculationMutation.mutate(buildPayload(formState))
  }

  const generalError = fieldErrors.nonFieldErrors
    ?? (calculationMutation.isError
      && Object.keys(fieldErrors).length === 0
      ? 'Не удалось выполнить расчёт. Проверьте данные и повторите попытку.'
      : null)

  return (
    <div className="page-stack mortgage-page trench-mortgage-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Финансовая модель</span>
          <h1>Траншевая ипотека</h1>
          <p>
            Рассчитайте поэтапную выдачу кредита с отдельными датами, долями
            и ставками. Последний транш автоматически покрывает остаток суммы.
          </p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to={marketCalculatorPath}>
            Рыночная ипотека
          </Link>
          <a className="button button--secondary" href="/mortgage/">
            Django-версия
          </a>
        </div>
      </header>

      {sampleIdentifier && !sessionQuery.data?.isAuthenticated ? (
        <p className="status-notice" role="status">
          Войдите в аккаунт, чтобы загрузить параметры сохранённого расчёта.
        </p>
      ) : null}
      {sampleQuery.isLoading ? (
        <p className="status-notice" role="status">
          Загружаем параметры сохранённого траншевого расчёта…
        </p>
      ) : null}
      {sampleQuery.isError ? (
        <p className="form-error" role="alert">
          Сохранённый расчёт не найден или недоступен. Можно заполнить форму
          вручную.
        </p>
      ) : null}

      <div className="mortgage-layout">
        <form className="calculator-card" onSubmit={handleSubmit}>
          <section
            className="calculator-section"
            aria-labelledby="trench-object-parameters"
          >
            <div className="calculator-section__heading">
              <span>01</span>
              <div>
                <h2 id="trench-object-parameters">Стоимость объекта</h2>
                <p>Цена и корректировка сделки</p>
              </div>
            </div>
            <div className="field-grid">
              <label className="form-field form-field--wide">
                <span>Базовая стоимость, ₽</span>
                <input
                  name="propertyCost"
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                  value={formState.propertyCost}
                  aria-invalid={Boolean(fieldErrors.propertyCost)}
                  aria-describedby={
                    fieldErrors.propertyCost ? 'propertyCost-error' : undefined
                  }
                  onChange={(event) => updateField('propertyCost', event.target.value)}
                />
                <FieldError fieldName="propertyCost" errors={fieldErrors} />
              </label>
              <fieldset className="form-field form-field--wide segmented-field">
                <legend>Тип корректировки</legend>
                <div className="segmented-control">
                  <label>
                    <input
                      name="trenchPriceAdjustmentType"
                      type="radio"
                      checked={formState.priceAdjustmentType === 'discount'}
                      onChange={() => updateField('priceAdjustmentType', 'discount')}
                    />
                    Скидка
                  </label>
                  <label>
                    <input
                      name="trenchPriceAdjustmentType"
                      type="radio"
                      checked={formState.priceAdjustmentType === 'markup'}
                      onChange={() => updateField('priceAdjustmentType', 'markup')}
                    />
                    Удорожание
                  </label>
                </div>
              </fieldset>
              <label className="form-field">
                <span>Размер корректировки</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  required
                  value={formState.priceAdjustmentValue}
                  aria-invalid={Boolean(fieldErrors.priceAdjustmentValue)}
                  aria-describedby={
                    fieldErrors.priceAdjustmentValue
                      ? 'priceAdjustmentValue-error'
                      : undefined
                  }
                  onChange={(event) => updateField(
                    'priceAdjustmentValue',
                    event.target.value,
                  )}
                />
                <FieldError
                  fieldName="priceAdjustmentValue"
                  errors={fieldErrors}
                />
              </label>
              <label className="form-field">
                <span>Единица</span>
                <select
                  value={formState.priceAdjustmentUnit}
                  onChange={(event) => updateField(
                    'priceAdjustmentUnit',
                    event.target.value as 'percent' | 'rubles',
                  )}
                >
                  <option value="percent">Проценты, %</option>
                  <option value="rubles">Рубли, ₽</option>
                </select>
              </label>
            </div>
          </section>

          <section
            className="calculator-section"
            aria-labelledby="trench-loan-parameters"
          >
            <div className="calculator-section__heading">
              <span>02</span>
              <div>
                <h2 id="trench-loan-parameters">Условия кредита</h2>
                <p>Взнос, общий срок и базовая ставка</p>
              </div>
            </div>
            <div className="field-grid">
              <label className="form-field">
                <span>Первоначальный взнос</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  required
                  value={formState.initialPaymentValue}
                  aria-invalid={Boolean(fieldErrors.initialPaymentValue)}
                  aria-describedby={
                    fieldErrors.initialPaymentValue
                      ? 'initialPaymentValue-error'
                      : undefined
                  }
                  onChange={(event) => updateField(
                    'initialPaymentValue',
                    event.target.value,
                  )}
                />
                <FieldError
                  fieldName="initialPaymentValue"
                  errors={fieldErrors}
                />
              </label>
              <label className="form-field">
                <span>Единица</span>
                <select
                  value={formState.initialPaymentUnit}
                  onChange={(event) => updateField(
                    'initialPaymentUnit',
                    event.target.value as 'percent' | 'rubles',
                  )}
                >
                  <option value="percent">Проценты, %</option>
                  <option value="rubles">Рубли, ₽</option>
                </select>
              </label>
              <label className="form-field">
                <span>Дата первоначального взноса</span>
                <input
                  type="date"
                  required
                  value={formState.initialPaymentDate}
                  aria-invalid={Boolean(fieldErrors.initialPaymentDate)}
                  aria-describedby={
                    fieldErrors.initialPaymentDate
                      ? 'initialPaymentDate-error'
                      : undefined
                  }
                  onChange={(event) => updateInitialPaymentDate(event.target.value)}
                />
                <FieldError
                  fieldName="initialPaymentDate"
                  errors={fieldErrors}
                />
              </label>
              <label className="form-field">
                <span>Срок ипотеки, месяцев</span>
                <input
                  aria-label="Срок ипотеки, месяцев"
                  type="number"
                  min="1"
                  max="600"
                  step="1"
                  required
                  value={formState.mortgageTermMonths}
                  aria-invalid={Boolean(fieldErrors.mortgageTermMonths)}
                  aria-describedby={
                    fieldErrors.mortgageTermMonths
                      ? 'mortgageTermMonths-error'
                      : undefined
                  }
                  onChange={(event) => updateField(
                    'mortgageTermMonths',
                    event.target.value,
                  )}
                />
                <small>{formatMonths(Number(formState.mortgageTermMonths) || 0)}</small>
                <FieldError
                  fieldName="mortgageTermMonths"
                  errors={fieldErrors}
                />
              </label>
              <label className="form-field">
                <span>Банк</span>
                <select
                  value={formState.bankId}
                  disabled={optionsQuery.isLoading}
                  onChange={(event) => setFormState((current) => ({
                    ...current,
                    bankId: event.target.value,
                    bankProgramId: '',
                  }))}
                >
                  <option value="">Без выбора</option>
                  {optionsQuery.data?.banks.map((bank) => (
                    <option value={bank.id} key={bank.id}>{bank.name}</option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                <span>Программа</span>
                <select
                  value={formState.bankProgramId}
                  disabled={!formState.bankId}
                  onChange={(event) => selectProgram(event.target.value)}
                >
                  <option value="">Ручные ставки</option>
                  {availablePrograms.map((program) => (
                    <option value={program.id} key={program.id}>
                      {program.programName} — {formatPercent(program.interestRate)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field form-field--wide">
                <span>Базовая годовая ставка, %</span>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  required
                  value={formState.annualRate}
                  aria-invalid={Boolean(fieldErrors.annualRate)}
                  aria-describedby={
                    fieldErrors.annualRate ? 'annualRate-error' : undefined
                  }
                  onChange={(event) => updateAnnualRate(event.target.value)}
                />
                <small>Изменение обновит ставки траншей без ручной настройки.</small>
                <FieldError fieldName="annualRate" errors={fieldErrors} />
              </label>
            </div>
          </section>

          <section
            className="calculator-section"
            aria-labelledby="trench-schedule-parameters"
          >
            <div className="calculator-section__heading">
              <span>03</span>
              <div>
                <h2 id="trench-schedule-parameters">График выдачи траншей</h2>
                <p>До пяти этапов с индивидуальной ставкой</p>
              </div>
            </div>
            <label className="form-field trench-count-field">
              <span>Количество траншей</span>
              <select
                value={formState.trenchCount}
                onChange={(event) => updateField(
                  'trenchCount',
                  Number(event.target.value),
                )}
              >
                {[1, 2, 3, 4, 5].map((count) => (
                  <option value={count} key={count}>{count}</option>
                ))}
              </select>
            </label>
            <div className="trench-input-list">
              {formState.trenches
                .slice(0, formState.trenchCount)
                .map((trench, index) => {
                  const isLast = index === formState.trenchCount - 1
                  const dateFieldName = `trenches.${index}.date`
                  const amountFieldName = `trenches.${index}.amountValue`
                  const rateFieldName = `trenches.${index}.annualRate`
                  return (
                    <fieldset className="trench-input-card" key={index}>
                      <legend>
                        Транш {index + 1}
                        {isLast ? <small>остаточный</small> : null}
                      </legend>
                      <div className="field-grid trench-input-grid">
                        <label className="form-field">
                          <span>Дата транша</span>
                          <input
                            type="date"
                            required
                            value={trench.date}
                            aria-invalid={Boolean(fieldErrors[dateFieldName])}
                            aria-describedby={
                              fieldErrors[dateFieldName]
                                ? `${dateFieldName}-error`
                                : undefined
                            }
                            onChange={(event) => updateTrench(
                              index,
                              'date',
                              event.target.value,
                            )}
                          />
                          <FieldError
                            fieldName={dateFieldName}
                            errors={fieldErrors}
                          />
                        </label>
                        {isLast ? (
                          <div className="trench-remainder-note" role="note">
                            <span>Сумма транша</span>
                            <strong>Остаток кредита</strong>
                            <small>Сервер рассчитает сумму и долю автоматически.</small>
                          </div>
                        ) : (
                          <>
                            <label className="form-field">
                              <span>Размер транша</span>
                              <input
                                type="number"
                                min="0.01"
                                step="0.01"
                                required
                                value={trench.amountValue}
                                aria-invalid={Boolean(fieldErrors[amountFieldName])}
                                aria-describedby={
                                  fieldErrors[amountFieldName]
                                    ? `${amountFieldName}-error`
                                    : undefined
                                }
                                onChange={(event) => updateTrench(
                                  index,
                                  'amountValue',
                                  event.target.value,
                                )}
                              />
                              <FieldError
                                fieldName={amountFieldName}
                                errors={fieldErrors}
                              />
                            </label>
                            <label className="form-field">
                              <span>Единица</span>
                              <select
                                value={trench.amountUnit}
                                onChange={(event) => updateTrench(
                                  index,
                                  'amountUnit',
                                  event.target.value as 'percent' | 'rubles',
                                )}
                              >
                                <option value="percent">Проценты, %</option>
                                <option value="rubles">Рубли, ₽</option>
                              </select>
                            </label>
                          </>
                        )}
                        <label className="form-field">
                          <span>Годовая ставка, %</span>
                          <input
                            type="number"
                            min="0"
                            max="100"
                            step="0.01"
                            required
                            value={trench.annualRate}
                            aria-invalid={Boolean(fieldErrors[rateFieldName])}
                            aria-describedby={
                              fieldErrors[rateFieldName]
                                ? `${rateFieldName}-error`
                                : undefined
                            }
                            onChange={(event) => updateTrench(
                              index,
                              'annualRate',
                              event.target.value,
                            )}
                          />
                          <FieldError
                            fieldName={rateFieldName}
                            errors={fieldErrors}
                          />
                        </label>
                      </div>
                    </fieldset>
                  )
                })}
            </div>
          </section>

          {generalError ? (
            <p className="form-error" role="alert">{generalError}</p>
          ) : null}
          <button
            className="button button--primary calculator-submit"
            type="submit"
            disabled={calculationMutation.isPending}
          >
            {calculationMutation.isPending
              ? 'Рассчитываем…'
              : 'Рассчитать траншевую ипотеку'}
          </button>
        </form>

        <aside className="calculator-reference" aria-label="Справочная информация">
          <span className="eyebrow">Ориентир</span>
          <strong>
            {optionsQuery.data ? formatPercent(optionsQuery.data.keyRate) : '—'}
          </strong>
          <p>Актуальная ключевая ставка из справочника приложения.</p>
          {optionsQuery.isError ? (
            <p className="reference-warning" role="status">
              Программы банков временно недоступны. Ручной расчёт продолжает
              работать.
            </p>
          ) : null}
          <Link to={`/mortgage/trench/calculations${
            customerIdentifier ? `?customerId=${customerIdentifier}` : ''
          }`}>
            История траншевых расчётов <span aria-hidden="true">→</span>
          </Link>
        </aside>
      </div>

      <div aria-live="polite">
        {calculationMutation.data ? (
          <TrenchMortgageResult
            key={calculationMutation.submittedAt}
            headingRef={resultHeadingRef}
            result={calculationMutation.data}
            summaryAction={(
              <section
                className="save-calculation-panel"
                aria-label="Сохранение траншевого расчёта"
              >
                <div>
                  <span className="eyebrow">История расчётов</span>
                  <h2>Сохранить этот сценарий</h2>
                  {!sessionQuery.data?.isAuthenticated ? (
                    <p>Войдите в аккаунт, чтобы сохранить расчёт.</p>
                  ) : propertyIdentifier ? (
                    <p>
                      Расчёт будет связан с выбранным объектом
                      {customerIdentifier ? ' и карточкой клиента' : ''}.
                    </p>
                  ) : (
                    <p>Для сохранения сначала выберите объект в каталоге.</p>
                  )}
                  {saveMutation.isError ? (
                    <p className="save-calculation-panel__error" role="alert">
                      Не удалось сохранить расчёт. Повторите попытку.
                    </p>
                  ) : null}
                </div>
                <div className="save-calculation-panel__actions">
                  {!sessionQuery.data?.isAuthenticated ? (
                    <a
                      className="button button--primary"
                      href={`/app/login?next=${encodeURIComponent(loginReturnPath)}`}
                    >
                      Войти
                    </a>
                  ) : propertyIdentifier && calculationMutation.variables ? (
                    saveMutation.data && customerIdentifier ? (
                      <Link
                        className="button button--primary"
                        to={`/customers/${customerIdentifier}`}
                      >
                        Открыть карточку клиента
                      </Link>
                    ) : saveMutation.data ? (
                      <Link
                        className="button button--primary"
                        to={`/mortgage/trench/calculations/${
                          saveMutation.data.id
                        }`}
                      >
                        Открыть сохранённый расчёт
                      </Link>
                    ) : (
                      <button
                        className="button button--primary"
                        type="button"
                        disabled={saveMutation.isPending}
                        onClick={() => saveMutation.mutate({
                          propertyId: propertyIdentifier,
                          parameters: calculationMutation.variables,
                          ...(customerIdentifier ? { customerId: customerIdentifier } : {}),
                        })}
                      >
                        {saveMutation.isPending
                          ? 'Сохраняем…'
                          : 'Сохранить расчёт'}
                      </button>
                    )
                  ) : (
                    <Link
                      className="button button--secondary"
                      to={`/properties${customerIdentifier ? `?customerId=${customerIdentifier}` : ''}`}
                    >
                      Выбрать объект
                    </Link>
                  )}
                </div>
              </section>
            )}
          />
        ) : null}
      </div>
    </div>
  )
}
