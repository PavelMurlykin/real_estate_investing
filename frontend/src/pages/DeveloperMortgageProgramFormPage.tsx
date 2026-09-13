import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  createDeveloperMortgageProgram,
  developerMortgageProgramDetailQueryOptions,
  developerMortgageProgramOptionsQueryOptions,
  sessionQueryOptions,
  updateDeveloperMortgageProgram,
} from '@/api/queries'
import type { DeveloperMortgageProgramWriteRequest } from '@/api/schemas'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type FormState = {
  companyGroupId: string
  realEstateComplexId: string
  bankId: string
  mortgageProgramId: string
  priceIncreasePercent: string
  gracePeriodMonths: string
  gracePeriodInterestRate: string
  minimumInitialPaymentPercent: string
  interestRate: string
  maximumLoanTermYears: string
  maximumLoanAmount: string
  rateDiscountPercent: string
  isActive: boolean
}
type FieldName = keyof Omit<FormState, 'isActive'>
type FormErrors = Partial<Record<FieldName, string>>

const emptyState: FormState = {
  companyGroupId: '',
  realEstateComplexId: '',
  bankId: '',
  mortgageProgramId: '',
  priceIncreasePercent: '',
  gracePeriodMonths: '',
  gracePeriodInterestRate: '',
  minimumInitialPaymentPercent: '',
  interestRate: '',
  maximumLoanTermYears: '',
  maximumLoanAmount: '',
  rateDiscountPercent: '',
  isActive: true,
}

function normalizeDecimal(value: string) {
  return value.trim().replace(',', '.')
}

function nullableDecimal(value: string) {
  return value.trim() ? normalizeDecimal(value) : null
}

function nullableInteger(value: string) {
  return value.trim() ? Number(value) : null
}

function decimalError(
  value: string,
  minimum: number,
  maximum: number,
) {
  if (!value.trim()) return undefined
  const numericValue = Number(normalizeDecimal(value))
  if (
    !Number.isFinite(numericValue)
    || numericValue < minimum
    || numericValue > maximum
  ) {
    return `Введите число от ${minimum} до ${maximum}.`
  }
  return undefined
}

function integerError(value: string) {
  if (!value.trim()) return undefined
  const numericValue = Number(value)
  if (!Number.isInteger(numericValue) || numericValue < 1 || numericValue > 32767) {
    return 'Введите целое число от 1 до 32767.'
  }
  return undefined
}

function firstError(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = firstError(item)
      if (message) return message
    }
  } else if (value && typeof value === 'object') {
    for (const item of Object.values(value)) {
      const message = firstError(item)
      if (message) return message
    }
  }
  return null
}

function serverFieldError(error: unknown, fieldName: FieldName) {
  if (!(error instanceof ApiError) || !error.details) return null
  if (typeof error.details !== 'object' || Array.isArray(error.details)) return null
  return firstError((error.details as Record<string, unknown>)[fieldName])
}

export function DeveloperMortgageProgramFormPage() {
  const { developerProgramId } = useParams()
  const isEditing = developerProgramId !== undefined
  const identifier = Number(developerProgramId ?? 0)
  const hasValidIdentifier = !isEditing
    || (Number.isInteger(identifier) && identifier > 0)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const initializedRef = useRef<number | null>(null)
  const [formState, setFormState] = useState<FormState>(emptyState)
  const [clientErrors, setClientErrors] = useState<FormErrors>({})
  const sessionQuery = useQuery(sessionQueryOptions)
  const canManage = sessionQuery.data?.capabilities.manageCatalogs === true
  const detailQuery = useQuery({
    ...developerMortgageProgramDetailQueryOptions(identifier),
    enabled: isEditing && hasValidIdentifier && canManage,
  })
  const selectedCompanyGroup = Number(formState.companyGroupId) || null
  const optionsQuery = useQuery({
    ...developerMortgageProgramOptionsQueryOptions(selectedCompanyGroup),
    enabled: canManage,
  })
  const mutation = useMutation({
    mutationFn: (payload: DeveloperMortgageProgramWriteRequest) => isEditing
      ? updateDeveloperMortgageProgram(identifier, payload)
      : createDeveloperMortgageProgram(payload),
    onSuccess: async (program) => {
      queryClient.setQueryData(
        ['developer-mortgage-program', program.id],
        program,
      )
      await queryClient.invalidateQueries({
        queryKey: ['developer-mortgage-programs'],
      })
      navigate(`/developer-programs/${program.id}`)
    },
  })
  useDocumentTitle(isEditing
    ? 'Редактирование программы застройщика'
    : 'Новая программа застройщика')

  useEffect(() => {
    const program = detailQuery.data
    if (!program || initializedRef.current === program.id) return
    setFormState({
      companyGroupId: String(program.companyGroupId),
      realEstateComplexId: program.realEstateComplexId?.toString() ?? '',
      bankId: String(program.bankId),
      mortgageProgramId: String(program.mortgageProgramId),
      priceIncreasePercent: program.priceIncreasePercent ?? '',
      gracePeriodMonths: program.gracePeriodMonths?.toString() ?? '',
      gracePeriodInterestRate: program.gracePeriodInterestRate ?? '',
      minimumInitialPaymentPercent: program.minimumInitialPaymentPercent ?? '',
      interestRate: program.interestRate ?? '',
      maximumLoanTermYears: program.maximumLoanTermYears?.toString() ?? '',
      maximumLoanAmount: program.maximumLoanAmount ?? '',
      rateDiscountPercent: program.rateDiscountPercent ?? '',
      isActive: program.isActive,
    })
    initializedRef.current = program.id
  }, [detailQuery.data])

  const setField = (fieldName: FieldName, value: string) => {
    setFormState((current) => ({
      ...current,
      [fieldName]: value,
      ...(fieldName === 'companyGroupId'
        ? { realEstateComplexId: '' }
        : {}),
    }))
    setClientErrors({})
    if (mutation.isError) mutation.reset()
  }

  const validate = () => {
    const errors: FormErrors = {}
    if (!formState.companyGroupId) errors.companyGroupId = 'Выберите группу компаний.'
    if (!formState.bankId) errors.bankId = 'Выберите банк.'
    if (!formState.mortgageProgramId) {
      errors.mortgageProgramId = 'Выберите ипотечную программу.'
    }
    errors.priceIncreasePercent = decimalError(
      formState.priceIncreasePercent,
      -9999.99,
      9999.99,
    )
    for (const fieldName of [
      'gracePeriodInterestRate',
      'minimumInitialPaymentPercent',
      'interestRate',
      'rateDiscountPercent',
    ] as const) {
      errors[fieldName] = decimalError(formState[fieldName], 0, 100)
    }
    errors.maximumLoanAmount = decimalError(
      formState.maximumLoanAmount,
      0,
      9_999_999_999_999.99,
    )
    errors.gracePeriodMonths = integerError(formState.gracePeriodMonths)
    errors.maximumLoanTermYears = integerError(
      formState.maximumLoanTermYears,
    )
    for (const fieldName of Object.keys(errors) as FieldName[]) {
      if (!errors[fieldName]) delete errors[fieldName]
    }
    setClientErrors(errors)
    return Object.keys(errors).length === 0
  }

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!validate()) return
    mutation.mutate({
      companyGroupId: Number(formState.companyGroupId),
      realEstateComplexId: formState.realEstateComplexId
        ? Number(formState.realEstateComplexId)
        : null,
      bankId: Number(formState.bankId),
      mortgageProgramId: Number(formState.mortgageProgramId),
      priceIncreasePercent: nullableDecimal(formState.priceIncreasePercent),
      gracePeriodMonths: nullableInteger(formState.gracePeriodMonths),
      gracePeriodInterestRate: nullableDecimal(
        formState.gracePeriodInterestRate,
      ),
      minimumInitialPaymentPercent: nullableDecimal(
        formState.minimumInitialPaymentPercent,
      ),
      interestRate: nullableDecimal(formState.interestRate),
      maximumLoanTermYears: nullableInteger(
        formState.maximumLoanTermYears,
      ),
      maximumLoanAmount: nullableDecimal(formState.maximumLoanAmount),
      rateDiscountPercent: nullableDecimal(formState.rateDiscountPercent),
      isActive: formState.isActive,
    })
  }

  const backLink = (
    <Link className="button button--secondary" to="/developer-programs">
      К списку
    </Link>
  )
  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Программа застройщика не найдена"
        description="Проверьте адрес или вернитесь к списку."
        action={backLink}
      />
    )
  }
  if (sessionQuery.isLoading) return <PageLoadingState />
  if (!sessionQuery.data?.isAuthenticated) {
    const nextPath = isEditing
      ? `/app/developer-programs/${identifier}/edit`
      : '/app/developer-programs/new'
    return (
      <EmptyState
        title="Войдите для управления программами"
        description="Изменение условий застройщиков доступно модераторам."
        action={(
          <a
            className="button button--primary"
            href={`/app/login?next=${encodeURIComponent(nextPath)}`}
          >Войти</a>
        )}
      />
    )
  }
  if (!canManage) {
    return (
      <EmptyState
        title="Недостаточно прав"
        description="Изменять программы могут модераторы каталога."
        action={backLink}
      />
    )
  }
  if (optionsQuery.isLoading || (isEditing && detailQuery.isLoading)) {
    return <PageLoadingState />
  }
  if (optionsQuery.isError || !optionsQuery.data) {
    return (
      <ErrorState
        title="Не удалось загрузить справочники формы"
        onRetry={() => void optionsQuery.refetch()}
      />
    )
  }
  if (isEditing && (detailQuery.isError || !detailQuery.data)) {
    return (
      <ErrorState
        title="Программа застройщика не найдена или недоступна"
        onRetry={() => void detailQuery.refetch()}
      />
    )
  }

  const options = optionsQuery.data
  const companyGroups = [...options.companyGroups]
  const banks = [...options.banks]
  const mortgagePrograms = [...options.mortgagePrograms]
  const realEstateComplexes = [...options.realEstateComplexes]
  const currentProgram = detailQuery.data
  if (currentProgram) {
    if (!companyGroups.some((option) => option.id === currentProgram.companyGroupId)) {
      companyGroups.push({ id: currentProgram.companyGroupId, name: currentProgram.companyGroupName })
    }
    if (!banks.some((option) => option.id === currentProgram.bankId)) {
      banks.push({ id: currentProgram.bankId, name: currentProgram.bankName })
    }
    if (!mortgagePrograms.some((option) => option.id === currentProgram.mortgageProgramId)) {
      mortgagePrograms.push({ id: currentProgram.mortgageProgramId, name: currentProgram.mortgageProgramName })
    }
    if (
      currentProgram.realEstateComplexId
      && currentProgram.realEstateComplexName
      && !realEstateComplexes.some(
        (option) => option.id === currentProgram.realEstateComplexId,
      )
    ) {
      realEstateComplexes.push({
        id: currentProgram.realEstateComplexId,
        name: currentProgram.complexDeveloperName
          ? `${currentProgram.realEstateComplexName} (${currentProgram.complexDeveloperName})`
          : currentProgram.realEstateComplexName,
      })
    }
  }
  const legacyUrl = currentProgram?.legacyEditUrl
    ?? '/bank/developer-programs/create/'
  const generalServerError = mutation.isError
    ? firstError((mutation.error as ApiError).details) ?? mutation.error.message
    : null

  const errorFor = (fieldName: FieldName) => (
    clientErrors[fieldName] || serverFieldError(mutation.error, fieldName)
  )
  return (
    <div className="page-stack developer-program-form-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Специальные ипотечные условия</span>
          <h1>{isEditing
            ? 'Редактирование программы застройщика'
            : 'Новая программа застройщика'}</h1>
          <p>Область действия, банк, программа и финансовые параметры.</p>
        </div>
        <div className="page-header__actions">
          {backLink}
          <a className="button button--secondary" href={legacyUrl}>Django-форма</a>
        </div>
      </header>

      <form className="customer-form developer-program-form" onSubmit={submit} noValidate>
        <section className="customer-form-section" aria-labelledby="developer-program-scope">
          <div className="customer-form-section__heading">
            <span aria-hidden="true">01</span>
            <div>
              <h2 id="developer-program-scope">Программа и область действия</h2>
              <p>Пустой ЖК означает, что условия действуют на всю группу.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Группа компаний *
              <select
                name="companyGroupId"
                value={formState.companyGroupId}
                onChange={(event) => setField('companyGroupId', event.target.value)}
                required
                autoFocus
                aria-invalid={Boolean(errorFor('companyGroupId'))}
              >
                <option value="">Выберите группу</option>
                {companyGroups.map((option) => (
                  <option value={option.id} key={option.id}>{option.name}</option>
                ))}
              </select>
              {errorFor('companyGroupId') ? <span className="field-error">{errorFor('companyGroupId')}</span> : null}
            </label>
            <label className="form-field">
              Жилой комплекс
              <select
                name="realEstateComplexId"
                value={formState.realEstateComplexId}
                onChange={(event) => setField('realEstateComplexId', event.target.value)}
                disabled={!formState.companyGroupId}
                aria-invalid={Boolean(errorFor('realEstateComplexId'))}
              >
                <option value="">Все ЖК группы</option>
                {realEstateComplexes.map((option) => (
                  <option value={option.id} key={option.id}>{option.name}</option>
                ))}
              </select>
              {errorFor('realEstateComplexId') ? <span className="field-error">{errorFor('realEstateComplexId')}</span> : null}
            </label>
            <label className="form-field">
              Банк *
              <select
                name="bankId"
                value={formState.bankId}
                onChange={(event) => setField('bankId', event.target.value)}
                required
                aria-invalid={Boolean(errorFor('bankId'))}
              >
                <option value="">Выберите банк</option>
                {banks.map((option) => (
                  <option value={option.id} key={option.id}>{option.name}</option>
                ))}
              </select>
              {errorFor('bankId') ? <span className="field-error">{errorFor('bankId')}</span> : null}
            </label>
            <label className="form-field">
              Ипотечная программа *
              <select
                name="mortgageProgramId"
                value={formState.mortgageProgramId}
                onChange={(event) => setField('mortgageProgramId', event.target.value)}
                required
                aria-invalid={Boolean(errorFor('mortgageProgramId'))}
              >
                <option value="">Выберите программу</option>
                {mortgagePrograms.map((option) => (
                  <option value={option.id} key={option.id}>{option.name}</option>
                ))}
              </select>
              {errorFor('mortgageProgramId') ? <span className="field-error">{errorFor('mortgageProgramId')}</span> : null}
            </label>
          </div>
          {Object.values(options.truncated).some(Boolean) ? (
            <p className="form-error" role="status">
              Показана только часть справочников. Полный набор доступен в Django-форме.
            </p>
          ) : null}
        </section>

        <section className="customer-form-section" aria-labelledby="developer-program-rates">
          <div className="customer-form-section__heading">
            <span aria-hidden="true">02</span>
            <div>
              <h2 id="developer-program-rates">Ставки и первоначальный взнос</h2>
              <p>Все процентные значения указываются в диапазоне от 0 до 100.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Удорожание, %
              <input
                name="priceIncreasePercent"
                type="number"
                step="0.01"
                inputMode="decimal"
                value={formState.priceIncreasePercent}
                onChange={(event) => setField('priceIncreasePercent', event.target.value)}
                aria-invalid={Boolean(errorFor('priceIncreasePercent'))}
              />
              {errorFor('priceIncreasePercent') ? <span className="field-error">{errorFor('priceIncreasePercent')}</span> : null}
            </label>
            <label className="form-field">
              Первоначальный взнос, %
              <input
                name="minimumInitialPaymentPercent"
                type="number"
                min="0"
                max="100"
                step="0.01"
                inputMode="decimal"
                value={formState.minimumInitialPaymentPercent}
                onChange={(event) => setField('minimumInitialPaymentPercent', event.target.value)}
                aria-invalid={Boolean(errorFor('minimumInitialPaymentPercent'))}
              />
              {errorFor('minimumInitialPaymentPercent') ? <span className="field-error">{errorFor('minimumInitialPaymentPercent')}</span> : null}
            </label>
            <label className="form-field">
              Годовая ставка, %
              <input
                name="interestRate"
                type="number"
                min="0"
                max="100"
                step="0.01"
                inputMode="decimal"
                value={formState.interestRate}
                onChange={(event) => setField('interestRate', event.target.value)}
                aria-invalid={Boolean(errorFor('interestRate'))}
              />
              {errorFor('interestRate') ? <span className="field-error">{errorFor('interestRate')}</span> : null}
            </label>
            <label className="form-field">
              Дисконт к ставке, п. п.
              <input
                name="rateDiscountPercent"
                type="number"
                min="0"
                max="100"
                step="0.01"
                inputMode="decimal"
                value={formState.rateDiscountPercent}
                onChange={(event) => setField('rateDiscountPercent', event.target.value)}
                aria-invalid={Boolean(errorFor('rateDiscountPercent'))}
              />
              {errorFor('rateDiscountPercent') ? <span className="field-error">{errorFor('rateDiscountPercent')}</span> : null}
            </label>
          </div>
        </section>
        <section className="customer-form-section" aria-labelledby="developer-program-grace">
          <div className="customer-form-section__heading">
            <span aria-hidden="true">03</span>
            <div>
              <h2 id="developer-program-grace">Льготный период</h2>
              <p>Продолжительность и ставка специального периода.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Срок льготного периода, мес.
              <input
                name="gracePeriodMonths"
                type="number"
                min="1"
                max="32767"
                step="1"
                inputMode="numeric"
                value={formState.gracePeriodMonths}
                onChange={(event) => setField('gracePeriodMonths', event.target.value)}
                aria-invalid={Boolean(errorFor('gracePeriodMonths'))}
              />
              {errorFor('gracePeriodMonths') ? <span className="field-error">{errorFor('gracePeriodMonths')}</span> : null}
            </label>
            <label className="form-field">
              Ставка льготного периода, %
              <input
                name="gracePeriodInterestRate"
                type="number"
                min="0"
                max="100"
                step="0.01"
                inputMode="decimal"
                value={formState.gracePeriodInterestRate}
                onChange={(event) => setField('gracePeriodInterestRate', event.target.value)}
                aria-invalid={Boolean(errorFor('gracePeriodInterestRate'))}
              />
              {errorFor('gracePeriodInterestRate') ? <span className="field-error">{errorFor('gracePeriodInterestRate')}</span> : null}
            </label>
          </div>
        </section>

        <section className="customer-form-section" aria-labelledby="developer-program-limits">
          <div className="customer-form-section__heading">
            <span aria-hidden="true">04</span>
            <div>
              <h2 id="developer-program-limits">Ограничения и статус</h2>
              <p>Максимальный срок, сумма кредита и доступность условий.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Максимальный срок, лет
              <input
                name="maximumLoanTermYears"
                type="number"
                min="1"
                max="32767"
                step="1"
                inputMode="numeric"
                value={formState.maximumLoanTermYears}
                onChange={(event) => setField('maximumLoanTermYears', event.target.value)}
                aria-invalid={Boolean(errorFor('maximumLoanTermYears'))}
              />
              {errorFor('maximumLoanTermYears') ? <span className="field-error">{errorFor('maximumLoanTermYears')}</span> : null}
            </label>
            <label className="form-field">
              Максимальная сумма, ₽
              <input
                name="maximumLoanAmount"
                type="number"
                min="0"
                max="9999999999999.99"
                step="0.01"
                inputMode="decimal"
                value={formState.maximumLoanAmount}
                onChange={(event) => setField('maximumLoanAmount', event.target.value)}
                aria-invalid={Boolean(errorFor('maximumLoanAmount'))}
              />
              {errorFor('maximumLoanAmount') ? <span className="field-error">{errorFor('maximumLoanAmount')}</span> : null}
            </label>
            <label className="developer-active-field form-field--wide">
              <input
                type="checkbox"
                checked={formState.isActive}
                onChange={(event) => {
                  setFormState((current) => ({
                    ...current,
                    isActive: event.target.checked,
                  }))
                  setClientErrors({})
                  if (mutation.isError) mutation.reset()
                }}
              />
              <span>
                <strong>Активная программа</strong>
                <small>Отключите, чтобы перевести условия на стоп.</small>
              </span>
            </label>
          </div>
        </section>
        {generalServerError ? <p className="form-error" role="alert">{generalServerError}</p> : null}
        <div className="customer-form-actions">
          {backLink}
          <button className="button button--primary" type="submit" disabled={mutation.isPending}>
            {mutation.isPending
              ? 'Сохраняем…'
              : isEditing ? 'Сохранить изменения' : 'Создать программу'}
          </button>
        </div>
      </form>
    </div>
  )
}
