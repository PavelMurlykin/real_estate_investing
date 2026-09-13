import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  bankDetailQueryOptions,
  bankOptionsQueryOptions,
  createBank,
  sessionQueryOptions,
  updateBank,
} from '@/api/queries'
import type { BankProgramWriteRequest, BankWriteRequest } from '@/api/schemas'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type BankProgramFormState = {
  clientKey: string
  mortgageProgramId: string
  interestRate: string
  minimumInitialPaymentPercent: string
  maximumLoanTermYears: string
}

type BankFormState = {
  name: string
  logoUrl: string
  isActive: boolean
  programs: BankProgramFormState[]
}

type ProgramFieldName = keyof Omit<BankProgramFormState, 'clientKey'>
type ProgramErrors = Partial<Record<ProgramFieldName, string>>
type ClientErrors = {
  name?: string
  logoUrl?: string
  programs?: string
  programRows: Record<string, ProgramErrors>
}

const emptyFormState: BankFormState = {
  name: '',
  logoUrl: '',
  isActive: true,
  programs: [],
}

function firstErrorMessage(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
  return null
}

function apiErrorDetails(error: unknown): Record<string, unknown> {
  if (
    !(error instanceof ApiError)
    || !error.details
    || typeof error.details !== 'object'
    || Array.isArray(error.details)
  ) {
    return {}
  }
  return error.details as Record<string, unknown>
}

function serverFieldError(error: unknown, fieldName: string) {
  return firstErrorMessage(apiErrorDetails(error)[fieldName])
}

function serverProgramError(
  error: unknown,
  rowIndex: number,
  fieldName: ProgramFieldName,
) {
  const programs = apiErrorDetails(error).programs
  if (!programs || typeof programs !== 'object') return null
  const rowErrors = Array.isArray(programs)
    ? programs[rowIndex]
    : (programs as Record<string, unknown>)[String(rowIndex)]
  if (!rowErrors || typeof rowErrors !== 'object' || Array.isArray(rowErrors)) {
    return null
  }
  return firstErrorMessage(
    (rowErrors as Record<string, unknown>)[fieldName],
  )
}

function normalizeDecimal(value: string) {
  return value.trim().replace(',', '.')
}

function validateDecimal(value: string, label: string) {
  const numberValue = Number(normalizeDecimal(value))
  if (!value.trim()) return `Заполните поле «${label}».`
  if (!Number.isFinite(numberValue) || numberValue < 0) {
    return `${label} должна быть неотрицательным числом.`
  }
  if (numberValue > 999.99) return `${label} не может превышать 999,99%.`
  return null
}

function buildProgramPayload(
  program: BankProgramFormState,
): BankProgramWriteRequest {
  return {
    mortgageProgramId: Number(program.mortgageProgramId),
    interestRate: normalizeDecimal(program.interestRate),
    minimumInitialPaymentPercent: normalizeDecimal(
      program.minimumInitialPaymentPercent,
    ),
    maximumLoanTermYears: program.maximumLoanTermYears.trim()
      ? Number(program.maximumLoanTermYears)
      : null,
  }
}

export function BankFormPage() {
  const { bankId } = useParams()
  const isEditing = bankId !== undefined
  const bankIdentifier = Number(bankId ?? 0)
  const hasValidIdentifier = !isEditing || (
    Number.isInteger(bankIdentifier) && bankIdentifier > 0
  )
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const initializedBankRef = useRef<number | null>(null)
  const nextProgramKeyRef = useRef(0)
  const [formState, setFormState] = useState(emptyFormState)
  const [clientErrors, setClientErrors] = useState<ClientErrors>({
    programRows: {},
  })
  const sessionQuery = useQuery(sessionQueryOptions)
  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  const bankQuery = useQuery({
    ...bankDetailQueryOptions(bankIdentifier),
    enabled: isEditing && hasValidIdentifier && canManageCatalogs,
  })
  const optionsQuery = useQuery({
    ...bankOptionsQueryOptions,
    enabled: canManageCatalogs,
  })
  const mutation = useMutation({
    mutationFn: (payload: BankWriteRequest) => (
      isEditing
        ? updateBank(bankIdentifier, payload)
        : createBank(payload)
    ),
    onSuccess: async (bank) => {
      queryClient.setQueryData(['bank', bank.id], bank)
      await queryClient.invalidateQueries({ queryKey: ['banks'] })
      navigate(`/banks/${bank.id}`)
    },
  })
  useDocumentTitle(isEditing ? 'Редактирование банка' : 'Новый банк')

  useEffect(() => {
    const bank = bankQuery.data
    if (!isEditing || !bank || initializedBankRef.current === bank.id) return
    setFormState({
      name: bank.name,
      logoUrl: bank.logoUrl,
      isActive: bank.isActive,
      programs: bank.programs.map((program) => ({
        clientKey: `existing-${program.id}`,
        mortgageProgramId: program.mortgageProgramId.toString(),
        interestRate: program.interestRate,
        minimumInitialPaymentPercent: program.minimumInitialPaymentPercent,
        maximumLoanTermYears:
          program.maximumLoanTermYears?.toString() ?? '',
      })),
    })
    initializedBankRef.current = bank.id
  }, [bankQuery.data, isEditing])

  const clearErrors = () => {
    setClientErrors({ programRows: {} })
    if (mutation.isError) mutation.reset()
  }

  const updateField = <FieldName extends keyof Omit<BankFormState, 'programs'>>(
    fieldName: FieldName,
    value: BankFormState[FieldName],
  ) => {
    setFormState((currentState) => ({
      ...currentState,
      [fieldName]: value,
    }))
    clearErrors()
  }

  const addProgram = () => {
    const clientKey = `new-${nextProgramKeyRef.current}`
    nextProgramKeyRef.current += 1
    setFormState((currentState) => ({
      ...currentState,
      programs: [
        ...currentState.programs,
        {
          clientKey,
          mortgageProgramId: '',
          interestRate: '',
          minimumInitialPaymentPercent: '',
          maximumLoanTermYears: '',
        },
      ],
    }))
    clearErrors()
  }

  const updateProgram = (
    clientKey: string,
    fieldName: ProgramFieldName,
    value: string,
  ) => {
    setFormState((currentState) => ({
      ...currentState,
      programs: currentState.programs.map((program) => (
        program.clientKey === clientKey
          ? { ...program, [fieldName]: value }
          : program
      )),
    }))
    clearErrors()
  }

  const removeProgram = (clientKey: string) => {
    setFormState((currentState) => ({
      ...currentState,
      programs: currentState.programs.filter(
        (program) => program.clientKey !== clientKey,
      ),
    }))
    clearErrors()
  }

  const validateForm = () => {
    const nextErrors: ClientErrors = { programRows: {} }
    if (!formState.name.trim()) nextErrors.name = 'Укажите название банка.'
    if (formState.logoUrl && !URL.canParse(formState.logoUrl)) {
      nextErrors.logoUrl = 'Укажите корректный URL логотипа.'
    }
    const selectedPrograms = new Set<string>()
    formState.programs.forEach((program) => {
      const errors: ProgramErrors = {}
      if (!program.mortgageProgramId) {
        errors.mortgageProgramId = 'Выберите ипотечную программу.'
      } else if (selectedPrograms.has(program.mortgageProgramId)) {
        errors.mortgageProgramId = 'Эта программа уже добавлена.'
      } else {
        selectedPrograms.add(program.mortgageProgramId)
      }
      const rateError = validateDecimal(program.interestRate, 'Ставка')
      if (rateError) errors.interestRate = rateError
      const paymentError = validateDecimal(
        program.minimumInitialPaymentPercent,
        'Первый взнос',
      )
      if (paymentError) errors.minimumInitialPaymentPercent = paymentError
      if (program.maximumLoanTermYears.trim()) {
        const term = Number(program.maximumLoanTermYears)
        if (!Number.isInteger(term) || term < 1 || term > 32767) {
          errors.maximumLoanTermYears = (
            'Срок должен быть целым числом от 1 до 32767.'
          )
        }
      }
      if (Object.keys(errors).length) {
        nextErrors.programRows[program.clientKey] = errors
      }
    })
    setClientErrors(nextErrors)
    return Object.keys(nextErrors).length === 1
      && Object.keys(nextErrors.programRows).length === 0
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!validateForm()) return
    mutation.mutate({
      name: formState.name.trim(),
      logoUrl: formState.logoUrl.trim(),
      isActive: formState.isActive,
      programs: formState.programs.map(buildProgramPayload),
    })
  }

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Банк не найден"
        description="Проверьте адрес или вернитесь к списку."
        action={(
          <Link className="button button--secondary" to="/banks">
            К списку
          </Link>
        )}
      />
    )
  }
  if (sessionQuery.isLoading) return <PageLoadingState />
  if (!sessionQuery.data?.isAuthenticated) {
    const nextPath = isEditing
      ? `/app/banks/${bankIdentifier}/edit`
      : '/app/banks/new'
    return (
      <EmptyState
        title="Войдите для управления банками"
        description="Изменение банковских условий доступно модераторам."
        action={(
          <a
            className="button button--primary"
            href={`/app/login?next=${encodeURIComponent(nextPath)}`}
          >
            Войти
          </a>
        )}
      />
    )
  }
  if (!canManageCatalogs) {
    return (
      <EmptyState
        title="Недостаточно прав"
        description="Изменять банки могут модераторы каталога."
        action={(
          <Link className="button button--secondary" to="/banks">
            К списку
          </Link>
        )}
      />
    )
  }
  if (optionsQuery.isLoading || (isEditing && bankQuery.isLoading)) {
    return <PageLoadingState />
  }
  if (optionsQuery.isError || !optionsQuery.data) {
    return (
      <ErrorState
        title="Не удалось загрузить ипотечные программы"
        onRetry={() => void optionsQuery.refetch()}
      />
    )
  }
  if (isEditing && (bankQuery.isError || !bankQuery.data)) {
    return (
      <ErrorState
        title="Банк не найден или недоступен"
        onRetry={() => void bankQuery.refetch()}
      />
    )
  }

  const mortgagePrograms = [...optionsQuery.data.mortgagePrograms]
  for (const existingProgram of bankQuery.data?.programs ?? []) {
    if (!mortgagePrograms.some(
      (program) => program.id === existingProgram.mortgageProgramId,
    )) {
      mortgagePrograms.push({
        id: existingProgram.mortgageProgramId,
        name: existingProgram.mortgageProgramName,
      })
    }
  }
  mortgagePrograms.sort((left, right) => left.name.localeCompare(
    right.name,
    'ru',
  ))
  const legacyFormUrl = isEditing && bankQuery.data
    ? bankQuery.data.legacyEditUrl
    : '/bank/banks/create/'
  const serverErrors = apiErrorDetails(mutation.error)
  const serverProgramsError = firstErrorMessage(serverErrors.programs)
  const hasGeneralServerError = mutation.isError && (
    Object.keys(serverErrors).length === 0
    || Boolean(firstErrorMessage(serverErrors.non_field_errors))
    || Boolean(firstErrorMessage(serverErrors.detail))
  )

  return (
    <div className="page-stack bank-form-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Финансовые справочники</span>
          <h1>{isEditing ? 'Редактирование банка' : 'Новый банк'}</h1>
          <p>Карточка банка и условия всех доступных ипотечных программ.</p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to="/banks">
            Отмена
          </Link>
          <a className="button button--secondary" href={legacyFormUrl}>
            Django-форма
          </a>
        </div>
      </header>

      <form className="customer-form bank-form" onSubmit={handleSubmit} noValidate>
        <section
          className="customer-form-section"
          aria-labelledby="bank-main-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">01</span>
            <div>
              <h2 id="bank-main-section">Основные данные</h2>
              <p>Название, логотип и доступность банка в рабочих формах.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Название *
              <input
                name="name"
                value={formState.name}
                onChange={(event) => updateField('name', event.target.value)}
                maxLength={255}
                required
                autoFocus
                autoComplete="organization"
                aria-invalid={Boolean(
                  clientErrors.name || serverFieldError(mutation.error, 'name'),
                )}
                aria-describedby="bank-name-error"
              />
              {(clientErrors.name
                || serverFieldError(mutation.error, 'name')) ? (
                  <span className="field-error" id="bank-name-error">
                    {clientErrors.name
                      || serverFieldError(mutation.error, 'name')}
                  </span>
                ) : null}
            </label>
            <label className="form-field">
              URL логотипа
              <input
                name="logoUrl"
                type="url"
                value={formState.logoUrl}
                onChange={(event) => updateField('logoUrl', event.target.value)}
                maxLength={1000}
                placeholder="https://example.ru/logo.svg"
                aria-invalid={Boolean(
                  clientErrors.logoUrl
                  || serverFieldError(mutation.error, 'logoUrl'),
                )}
                aria-describedby="bank-logo-url-hint bank-logoUrl-error"
              />
              <small id="bank-logo-url-hint">
                Используйте HTTPS-адрес официального логотипа банка.
              </small>
              {(clientErrors.logoUrl
                || serverFieldError(mutation.error, 'logoUrl')) ? (
                  <span className="field-error" id="bank-logoUrl-error">
                    {clientErrors.logoUrl
                      || serverFieldError(mutation.error, 'logoUrl')}
                  </span>
                ) : null}
            </label>
            <label className="developer-active-field form-field--wide">
              <input
                type="checkbox"
                checked={formState.isActive}
                onChange={(event) => updateField(
                  'isActive',
                  event.target.checked,
                )}
              />
              <span>
                <strong>Активный банк</strong>
                <small>Банк доступен для выбора в ипотечных расчётах.</small>
              </span>
            </label>
          </div>
        </section>

        <section
          className="customer-form-section bank-programs-section"
          aria-labelledby="bank-programs-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">02</span>
            <div>
              <h2 id="bank-programs-section">Ипотечные программы</h2>
              <p>Ставка, первый взнос и максимальный срок по каждой программе.</p>
              <button
                className="button button--secondary bank-add-program"
                type="button"
                onClick={addProgram}
              >
                Добавить программу
              </button>
            </div>
          </div>
          <div className="bank-program-editors">
            {optionsQuery.data.truncated ? (
              <p className="form-error" role="alert">
                Показана только первая часть программ. Если нужной программы
                нет, завершите редактирование в сохранённой Django-форме.
              </p>
            ) : null}
            {formState.programs.length === 0 ? (
              <div className="bank-program-empty">
                <strong>Программы не добавлены</strong>
                <p>Банк можно сохранить без программ и заполнить их позже.</p>
              </div>
            ) : null}
            {formState.programs.map((program, rowIndex) => {
              const rowErrors = clientErrors.programRows[program.clientKey]
                ?? {}
              const errorFor = (fieldName: ProgramFieldName) => (
                rowErrors[fieldName]
                || serverProgramError(mutation.error, rowIndex, fieldName)
              )
              return (
                <fieldset
                  className="bank-program-editor"
                  key={program.clientKey}
                >
                  <legend>Программа {rowIndex + 1}</legend>
                  <div className="bank-program-editor__heading">
                    <strong>Условия программы</strong>
                    <button
                      className="text-button text-button--danger"
                      type="button"
                      onClick={() => removeProgram(program.clientKey)}
                      aria-label={`Удалить программу ${rowIndex + 1}`}
                    >
                      Удалить
                    </button>
                  </div>
                  <div className="field-grid bank-program-fields">
                    <label className="form-field form-field--wide">
                      Ипотечная программа *
                      <select
                        name={`programs.${rowIndex}.mortgageProgramId`}
                        value={program.mortgageProgramId}
                        onChange={(event) => updateProgram(
                          program.clientKey,
                          'mortgageProgramId',
                          event.target.value,
                        )}
                        required
                        aria-invalid={Boolean(errorFor('mortgageProgramId'))}
                        aria-describedby={`bank-program-${rowIndex}-mortgageProgramId-error`}
                      >
                        <option value="">Выберите программу</option>
                        {mortgagePrograms.map((mortgageProgram) => (
                          <option
                            value={mortgageProgram.id}
                            key={mortgageProgram.id}
                          >
                            {mortgageProgram.name}
                          </option>
                        ))}
                      </select>
                      {errorFor('mortgageProgramId') ? (
                        <span
                          className="field-error"
                          id={`bank-program-${rowIndex}-mortgageProgramId-error`}
                        >
                          {errorFor('mortgageProgramId')}
                        </span>
                      ) : null}
                    </label>
                    <label className="form-field">
                      Ставка, % *
                      <input
                        name={`programs.${rowIndex}.interestRate`}
                        type="number"
                        min="0"
                        max="999.99"
                        step="0.01"
                        inputMode="decimal"
                        value={program.interestRate}
                        onChange={(event) => updateProgram(
                          program.clientKey,
                          'interestRate',
                          event.target.value,
                        )}
                        required
                        aria-invalid={Boolean(errorFor('interestRate'))}
                        aria-describedby={`bank-program-${rowIndex}-interestRate-error`}
                      />
                      {errorFor('interestRate') ? (
                        <span
                          className="field-error"
                          id={`bank-program-${rowIndex}-interestRate-error`}
                        >
                          {errorFor('interestRate')}
                        </span>
                      ) : null}
                    </label>
                    <label className="form-field">
                      Первый взнос, % *
                      <input
                        name={`programs.${rowIndex}.minimumInitialPaymentPercent`}
                        type="number"
                        min="0"
                        max="999.99"
                        step="0.01"
                        inputMode="decimal"
                        value={program.minimumInitialPaymentPercent}
                        onChange={(event) => updateProgram(
                          program.clientKey,
                          'minimumInitialPaymentPercent',
                          event.target.value,
                        )}
                        required
                        aria-invalid={Boolean(
                          errorFor('minimumInitialPaymentPercent'),
                        )}
                        aria-describedby={`bank-program-${rowIndex}-minimumInitialPaymentPercent-error`}
                      />
                      {errorFor('minimumInitialPaymentPercent') ? (
                        <span
                          className="field-error"
                          id={`bank-program-${rowIndex}-minimumInitialPaymentPercent-error`}
                        >
                          {errorFor('minimumInitialPaymentPercent')}
                        </span>
                      ) : null}
                    </label>
                    <label className="form-field">
                      Максимальный срок, лет
                      <input
                        name={`programs.${rowIndex}.maximumLoanTermYears`}
                        type="number"
                        min="1"
                        max="32767"
                        step="1"
                        inputMode="numeric"
                        value={program.maximumLoanTermYears}
                        onChange={(event) => updateProgram(
                          program.clientKey,
                          'maximumLoanTermYears',
                          event.target.value,
                        )}
                        aria-invalid={Boolean(
                          errorFor('maximumLoanTermYears'),
                        )}
                        aria-describedby={`bank-program-${rowIndex}-maximumLoanTermYears-error`}
                      />
                      {errorFor('maximumLoanTermYears') ? (
                        <span
                          className="field-error"
                          id={`bank-program-${rowIndex}-maximumLoanTermYears-error`}
                        >
                          {errorFor('maximumLoanTermYears')}
                        </span>
                      ) : null}
                    </label>
                  </div>
                </fieldset>
              )
            })}
            {(clientErrors.programs || serverProgramsError) ? (
              <p className="form-error" role="alert">
                {clientErrors.programs || serverProgramsError}
              </p>
            ) : null}
          </div>
        </section>

        {hasGeneralServerError ? (
          <p className="form-error" role="alert">
            {firstErrorMessage(serverErrors.non_field_errors)
              || firstErrorMessage(serverErrors.detail)
              || 'Не удалось сохранить банк. Повторите попытку.'}
          </p>
        ) : null}
        <div className="customer-form-actions">
          <Link className="button button--secondary" to="/banks">
            Отмена
          </Link>
          <button
            className="button button--primary"
            type="submit"
            disabled={mutation.isPending}
          >
            {mutation.isPending
              ? 'Сохраняем…'
              : isEditing ? 'Сохранить изменения' : 'Создать банк'}
          </button>
        </div>
      </form>
    </div>
  )
}
