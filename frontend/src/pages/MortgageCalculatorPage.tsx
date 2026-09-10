import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  calculateMortgage,
  mortgageOptionsQueryOptions,
  saveMortgageCalculation,
  savedMortgageCalculationDetailQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type { MortgageCalculationRequest } from '@/api/schemas'
import { MortgageResult } from '@/features/mortgage/MortgageResult'
import {
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

export function MortgageCalculatorPage() {
  useDocumentTitle('Ипотечный калькулятор')
  const [searchParameters] = useSearchParams()
  const queryClient = useQueryClient()
  const optionsQuery = useQuery(mortgageOptionsQueryOptions)
  const sessionQuery = useQuery(sessionQueryOptions)
  const resultHeadingRef = useRef<HTMLHeadingElement>(null)
  const appliedSampleIdentifierRef = useRef<number | null>(null)
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
    ...savedMortgageCalculationDetailQueryOptions(sampleIdentifier ?? 0),
    enabled: sessionQuery.data?.isAuthenticated === true
      && sampleIdentifier !== null,
  })
  const calculationQueryString = searchParameters.toString()
  const loginReturnPath = `/app/mortgage${
    calculationQueryString ? `?${calculationQueryString}` : ''
  }`
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
  const saveMutation = useMutation({
    mutationFn: saveMortgageCalculation,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['saved-mortgage-calculations'],
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

  useEffect(() => {
    if (
      !sampleQuery.data
      || appliedSampleIdentifierRef.current === sampleQuery.data.id
    ) {
      return
    }
    const assumptions = sampleQuery.data.calculation.assumptions
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
      hasGracePeriod: assumptions.hasGracePeriod,
      gracePeriodTermMonths: String(
        assumptions.gracePeriodTermMonths || 12,
      ),
      gracePeriodRate: assumptions.gracePeriodRate ?? '6',
    })
    appliedSampleIdentifierRef.current = sampleQuery.data.id
  }, [sampleQuery.data])

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
    saveMutation.reset()
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
            графиком. Авторизованные пользователи могут сохранить результат
            для объекта из каталога.
          </p>
        </div>
        <div className="page-header__actions">
          <Link
            className="button button--secondary"
            to={`/mortgage/trench${
              calculationQueryString ? `?${calculationQueryString}` : ''
            }`}
          >
            Траншевая ипотека
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
          Загружаем параметры сохранённого расчёта…
        </p>
      ) : null}
      {sampleQuery.isError ? (
        <p className="form-error" role="alert">
          Сохранённый расчёт не найден или недоступен. Можно заполнить форму
          вручную.
        </p>
      ) : null}

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
          <Link to={`/properties${customerIdentifier ? `?customerId=${customerIdentifier}` : ''}`}>
            Выбрать объект в каталоге <span aria-hidden="true">→</span>
          </Link>
        </aside>
      </div>

      <div aria-live="polite">
        {calculationMutation.data ? (
          <MortgageResult
            key={calculationMutation.submittedAt}
            headingRef={resultHeadingRef}
            result={calculationMutation.data}
            summaryAction={(
              <section className="save-calculation-panel" aria-label="Сохранение расчёта">
                <div>
                  <span className="eyebrow">История расчётов</span>
                  <h2>Сохранить этот сценарий</h2>
                  {!sessionQuery.data?.isAuthenticated ? (
                    <p>Войдите в аккаунт, чтобы сохранить расчёт и вернуться к нему позже.</p>
                  ) : propertyIdentifier ? (
                    <p>
                      Расчёт будет связан с выбранным объектом
                      {customerIdentifier ? ' и карточкой клиента' : ''}.
                    </p>
                  ) : (
                    <p>Для сохранения сначала выберите объект в каталоге недвижимости.</p>
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
                      href={`/users/login/?next=${encodeURIComponent(loginReturnPath)}`}
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
                        to={`/mortgage/calculations/${saveMutation.data.id}`}
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
                        {saveMutation.isPending ? 'Сохраняем…' : 'Сохранить расчёт'}
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
