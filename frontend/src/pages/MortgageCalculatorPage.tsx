import { useMutation, useQuery } from '@tanstack/react-query'
import type { FormEvent, ReactNode, RefObject } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { calculateMortgage, mortgageOptionsQueryOptions } from '@/api/queries'
import type {
  MortgageCalculationRequest,
  MortgageCalculationResponse,
} from '@/api/schemas'
import {
  formatCurrency,
  formatDate,
  formatMonths,
  formatPercent,
} from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'

type MortgageFormState = {
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
  hasGracePeriod: boolean
  gracePeriodTermMonths: string
  gracePeriodRate: string
}

type FieldErrors = Record<string, string>

function getLocalDateInputValue() {
  const currentDate = new Date()
  const timezoneOffset = currentDate.getTimezoneOffset() * 60_000
  return new Date(currentDate.getTime() - timezoneOffset)
    .toISOString()
    .slice(0, 10)
}

function extractFieldErrors(error: unknown): FieldErrors {
  if (!(error instanceof ApiError) || !error.details) return {}
  if (typeof error.details !== 'object' || Array.isArray(error.details)) return {}

  return Object.fromEntries(
    Object.entries(error.details).flatMap(([fieldName, messages]) => {
      if (Array.isArray(messages) && typeof messages[0] === 'string') {
        return [[fieldName, messages[0]]]
      }
      if (typeof messages === 'string') return [[fieldName, messages]]
      return []
    }),
  )
}

function FieldError({ fieldName, errors }: { fieldName: string; errors: FieldErrors }) {
  const message = errors[fieldName]
  if (!message) return null
  return <span className="field-error" id={`${fieldName}-error`}>{message}</span>
}

function SummaryItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="mortgage-summary__item">
      <span>{label}</span>
      <strong>{children}</strong>
    </div>
  )
}

function MortgageResult({
  result,
  headingRef,
}: {
  result: MortgageCalculationResponse
  headingRef: RefObject<HTMLHeadingElement | null>
}) {
  const [showFullSchedule, setShowFullSchedule] = useState(false)
  const visibleSchedule = showFullSchedule
    ? result.schedule
    : result.schedule.slice(0, 12)

  return (
    <div className="mortgage-result">
      <section className="mortgage-summary" aria-labelledby="mortgage-result-title">
        <div className="mortgage-summary__heading">
          <div>
            <span className="eyebrow">Результат расчёта</span>
            <h2 id="mortgage-result-title" ref={headingRef} tabIndex={-1}>
              Параметры кредита
            </h2>
          </div>
          <span className="mortgage-summary__term">
            {formatMonths(result.assumptions.mortgageTermMonths)}
          </span>
        </div>
        <div className="mortgage-summary__primary">
          <span>Ежемесячный платёж</span>
          <strong>{formatCurrency(result.summary.mainMonthlyPayment)}</strong>
          <small>до {formatDate(result.summary.mortgageEndDate)}</small>
        </div>
        <div className="mortgage-summary__grid">
          <SummaryItem label="Стоимость после корректировки">
            {formatCurrency(result.assumptions.finalPropertyCost)}
          </SummaryItem>
          <SummaryItem label="Первоначальный взнос">
            {formatCurrency(result.assumptions.initialPaymentRubles)}
          </SummaryItem>
          <SummaryItem label="Сумма кредита">
            {formatCurrency(result.summary.loanAmount)}
          </SummaryItem>
          <SummaryItem label="Переплата">
            {formatCurrency(result.summary.overpayment)}
          </SummaryItem>
          <SummaryItem label="Всего выплат">
            {formatCurrency(result.summary.totalPayments)}
          </SummaryItem>
          <SummaryItem label="Годовая ставка">
            {formatPercent(result.assumptions.annualRate)}
          </SummaryItem>
        </div>
        {result.summary.graceMonthlyPayment ? (
          <div className="grace-result">
            Льготный платёж: <strong>
              {formatCurrency(result.summary.graceMonthlyPayment)}
            </strong>{' '}
            до {formatDate(result.summary.gracePeriodEndDate ?? '')}
          </div>
        ) : null}
      </section>

      <section className="schedule-panel" aria-labelledby="schedule-title">
        <div className="section-heading section-heading--with-action">
          <div>
            <span className="eyebrow">Детализация</span>
            <h2 id="schedule-title">График платежей</h2>
          </div>
          {result.schedule.length > 12 ? (
            <button
              className="button button--secondary"
              type="button"
              onClick={() => setShowFullSchedule((current) => !current)}
            >
              {showFullSchedule ? 'Первые 12 платежей' : 'Показать весь график'}
            </button>
          ) : null}
        </div>
        <div className="mortgage-schedule-wrapper">
          <table className="property-table mortgage-schedule">
            <caption className="visually-hidden">График ежемесячных платежей</caption>
            <thead>
              <tr>
                <th scope="col">№</th>
                <th scope="col">Дата</th>
                <th scope="col">Платёж</th>
                <th scope="col">Проценты</th>
                <th scope="col">Основной долг</th>
                <th scope="col">Остаток</th>
              </tr>
            </thead>
            <tbody>
              {visibleSchedule.map((payment) => (
                <tr key={payment.paymentNumber}>
                  <td>{payment.paymentNumber}</td>
                  <td>{formatDate(payment.paymentDate)}</td>
                  <td><strong>{formatCurrency(payment.paymentAmount)}</strong></td>
                  <td>{formatCurrency(payment.interestAmount)}</td>
                  <td>{formatCurrency(payment.principalAmount)}</td>
                  <td>{formatCurrency(payment.remainingDebt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

export function MortgageCalculatorPage() {
  useDocumentTitle('Ипотечный калькулятор')
  const [searchParameters] = useSearchParams()
  const optionsQuery = useQuery(mortgageOptionsQueryOptions)
  const resultHeadingRef = useRef<HTMLHeadingElement>(null)
  const [formState, setFormState] = useState<MortgageFormState>(() => ({
    propertyCost: searchParameters.get('propertyCost') ?? '5000000',
    priceAdjustmentType: 'discount',
    priceAdjustmentUnit: 'percent',
    priceAdjustmentValue: '0',
    initialPaymentUnit: 'percent',
    initialPaymentValue: '20',
    initialPaymentDate: '',
    mortgageTermMonths: '360',
    annualRate: '15',
    bankId: '',
    bankProgramId: '',
    hasGracePeriod: false,
    gracePeriodTermMonths: '12',
    gracePeriodRate: '6',
  }))
  const calculationMutation = useMutation({ mutationFn: calculateMortgage })
  const fieldErrors = extractFieldErrors(calculationMutation.error)
  const initialPaymentDate = formState.initialPaymentDate
    || optionsQuery.data?.defaultInitialPaymentDate
    || getLocalDateInputValue()
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

  const updateField = <FieldName extends keyof MortgageFormState>(
    fieldName: FieldName,
    value: MortgageFormState[FieldName],
  ) => setFormState((current) => ({ ...current, [fieldName]: value }))

  const selectProgram = (programIdentifier: string) => {
    const program = optionsQuery.data?.programs.find(
      (item) => String(item.id) === programIdentifier,
    )
    setFormState((current) => {
      if (!program) return { ...current, bankProgramId: '' }
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
      }
    })
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const payload: MortgageCalculationRequest = {
      propertyCost: formState.propertyCost,
      priceAdjustmentType: formState.priceAdjustmentType,
      priceAdjustmentUnit: formState.priceAdjustmentUnit,
      priceAdjustmentValue: formState.priceAdjustmentValue,
      initialPaymentUnit: formState.initialPaymentUnit,
      initialPaymentValue: formState.initialPaymentValue,
      initialPaymentDate,
      mortgageTermMonths: Number(formState.mortgageTermMonths),
      annualRate: formState.annualRate,
      hasGracePeriod: formState.hasGracePeriod,
    }
    if (formState.hasGracePeriod) {
      payload.gracePeriodTermMonths = Number(formState.gracePeriodTermMonths)
      payload.gracePeriodRate = formState.gracePeriodRate
    }
    calculationMutation.mutate(payload)
  }

  const hasGeneralError = calculationMutation.isError
    && Object.keys(fieldErrors).length === 0

  return (
    <div className="page-stack mortgage-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Финансовая модель</span>
          <h1>Ипотечный калькулятор</h1>
          <p>
            Сравните параметры сделки и получите аннуитетный платёж с полным
            графиком. Расчёт не сохраняет персональные данные.
          </p>
        </div>
        <a className="button button--secondary" href="/mortgage/">
          Прежняя версия
        </a>
      </header>

      <div className="mortgage-layout">
        <form className="calculator-card" onSubmit={handleSubmit} noValidate={false}>
          <section className="calculator-section" aria-labelledby="object-parameters">
            <div className="calculator-section__heading">
              <span>01</span>
              <div><h2 id="object-parameters">Стоимость объекта</h2><p>Цена и корректировка сделки</p></div>
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
                  aria-describedby={fieldErrors.propertyCost ? 'propertyCost-error' : undefined}
                  onChange={(event) => updateField('propertyCost', event.target.value)}
                />
                <FieldError fieldName="propertyCost" errors={fieldErrors} />
              </label>
              <fieldset className="form-field form-field--wide segmented-field">
                <legend>Тип корректировки</legend>
                <div className="segmented-control">
                  <label><input name="priceAdjustmentType" type="radio" checked={formState.priceAdjustmentType === 'discount'} onChange={() => updateField('priceAdjustmentType', 'discount')} />Скидка</label>
                  <label><input name="priceAdjustmentType" type="radio" checked={formState.priceAdjustmentType === 'markup'} onChange={() => updateField('priceAdjustmentType', 'markup')} />Удорожание</label>
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
                  aria-describedby={fieldErrors.priceAdjustmentValue ? 'priceAdjustmentValue-error' : undefined}
                  onChange={(event) => updateField('priceAdjustmentValue', event.target.value)}
                />
                <FieldError fieldName="priceAdjustmentValue" errors={fieldErrors} />
              </label>
              <label className="form-field"><span>Единица</span><select value={formState.priceAdjustmentUnit} onChange={(event) => updateField('priceAdjustmentUnit', event.target.value as 'percent' | 'rubles')}><option value="percent">Проценты, %</option><option value="rubles">Рубли, ₽</option></select></label>
            </div>
          </section>

          <section className="calculator-section" aria-labelledby="loan-parameters">
            <div className="calculator-section__heading">
              <span>02</span>
              <div><h2 id="loan-parameters">Условия кредита</h2><p>Взнос, срок и ставка</p></div>
            </div>
            <div className="field-grid">
              <label className="form-field"><span>Первоначальный взнос</span><input type="number" min="0" step="0.01" required value={formState.initialPaymentValue} aria-invalid={Boolean(fieldErrors.initialPaymentValue)} aria-describedby={fieldErrors.initialPaymentValue ? 'initialPaymentValue-error' : undefined} onChange={(event) => updateField('initialPaymentValue', event.target.value)} /><FieldError fieldName="initialPaymentValue" errors={fieldErrors} /></label>
              <label className="form-field"><span>Единица</span><select value={formState.initialPaymentUnit} onChange={(event) => updateField('initialPaymentUnit', event.target.value as 'percent' | 'rubles')}><option value="percent">Проценты, %</option><option value="rubles">Рубли, ₽</option></select></label>
              <label className="form-field"><span>Дата первого взноса</span><input type="date" required value={initialPaymentDate} aria-invalid={Boolean(fieldErrors.initialPaymentDate)} aria-describedby={fieldErrors.initialPaymentDate ? 'initialPaymentDate-error' : undefined} onChange={(event) => updateField('initialPaymentDate', event.target.value)} /><FieldError fieldName="initialPaymentDate" errors={fieldErrors} /></label>
              <label className="form-field"><span>Срок ипотеки, месяцев</span><input aria-label="Срок ипотеки, месяцев" type="number" min="1" max="600" step="1" required value={formState.mortgageTermMonths} aria-invalid={Boolean(fieldErrors.mortgageTermMonths)} aria-describedby={fieldErrors.mortgageTermMonths ? 'mortgageTermMonths-error' : undefined} onChange={(event) => updateField('mortgageTermMonths', event.target.value)} /><small>{formatMonths(Number(formState.mortgageTermMonths) || 0)}</small><FieldError fieldName="mortgageTermMonths" errors={fieldErrors} /></label>
              <label className="form-field"><span>Банк</span><select value={formState.bankId} disabled={optionsQuery.isLoading} onChange={(event) => setFormState((current) => ({ ...current, bankId: event.target.value, bankProgramId: '' }))}><option value="">Без выбора</option>{optionsQuery.data?.banks.map((bank) => <option value={bank.id} key={bank.id}>{bank.name}</option>)}</select></label>
              <label className="form-field"><span>Программа</span><select value={formState.bankProgramId} disabled={!formState.bankId} onChange={(event) => selectProgram(event.target.value)}><option value="">Ручная ставка</option>{availablePrograms.map((program) => <option value={program.id} key={program.id}>{program.programName} — {formatPercent(program.interestRate)}</option>)}</select></label>
              <label className="form-field form-field--wide"><span>Годовая ставка, %</span><input type="number" min="0.01" max="100" step="0.01" required value={formState.annualRate} aria-invalid={Boolean(fieldErrors.annualRate)} aria-describedby={fieldErrors.annualRate ? 'annualRate-error' : undefined} onChange={(event) => updateField('annualRate', event.target.value)} /><FieldError fieldName="annualRate" errors={fieldErrors} /></label>
            </div>
          </section>

          <section className="calculator-section" aria-labelledby="grace-parameters">
            <div className="calculator-section__heading">
              <span>03</span>
              <div><h2 id="grace-parameters">Льготный период</h2><p>Дополнительный этап со сниженной ставкой</p></div>
            </div>
            <label className="toggle-field"><input type="checkbox" checked={formState.hasGracePeriod} onChange={(event) => updateField('hasGracePeriod', event.target.checked)} /><span>Использовать льготный период</span></label>
            {formState.hasGracePeriod ? (
              <div className="field-grid grace-fields">
                <label className="form-field"><span>Срок льготного периода, месяцев</span><input type="number" min="1" max="599" required value={formState.gracePeriodTermMonths} aria-invalid={Boolean(fieldErrors.gracePeriodTermMonths)} aria-describedby={fieldErrors.gracePeriodTermMonths ? 'gracePeriodTermMonths-error' : undefined} onChange={(event) => updateField('gracePeriodTermMonths', event.target.value)} /><FieldError fieldName="gracePeriodTermMonths" errors={fieldErrors} /></label>
                <label className="form-field"><span>Ставка, %</span><input type="number" min="0.01" max="100" step="0.01" required value={formState.gracePeriodRate} aria-invalid={Boolean(fieldErrors.gracePeriodRate)} aria-describedby={fieldErrors.gracePeriodRate ? 'gracePeriodRate-error' : undefined} onChange={(event) => updateField('gracePeriodRate', event.target.value)} /><FieldError fieldName="gracePeriodRate" errors={fieldErrors} /></label>
              </div>
            ) : null}
          </section>

          {hasGeneralError ? <p className="form-error" role="alert">Не удалось выполнить расчёт. Проверьте данные и повторите попытку.</p> : null}
          <button className="button button--primary calculator-submit" type="submit" disabled={calculationMutation.isPending}>
            {calculationMutation.isPending ? 'Рассчитываем…' : 'Рассчитать ипотеку'}
          </button>
        </form>

        <aside className="calculator-reference" aria-label="Справочная информация">
          <span className="eyebrow">Ориентир</span>
          <strong>{optionsQuery.data ? formatPercent(optionsQuery.data.keyRate) : '—'}</strong>
          <p>Актуальная ключевая ставка из справочника приложения.</p>
          {optionsQuery.isError ? <p className="reference-warning" role="status">Программы банков временно недоступны. Ручной расчёт продолжает работать.</p> : null}
          <Link to="/properties">Выбрать объект в каталоге <span aria-hidden="true">→</span></Link>
        </aside>
      </div>

      <div aria-live="polite">
        {calculationMutation.data ? (
          <MortgageResult
            key={calculationMutation.submittedAt}
            headingRef={resultHeadingRef}
            result={calculationMutation.data}
          />
        ) : null}
      </div>
    </div>
  )
}
