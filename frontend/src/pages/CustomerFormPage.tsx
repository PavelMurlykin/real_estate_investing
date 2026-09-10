import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  createCustomer,
  customerDetailQueryOptions,
  customerFormOptionsQueryOptions,
  sessionQueryOptions,
  updateCustomer,
} from '@/api/queries'
import type { CustomerWriteRequest } from '@/api/schemas'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type CustomerFormState = {
  firstName: string
  lastName: string
  phone: string
  email: string
  age: string
  birthDate: string
  birthYear: string
  residenceCityId: string
  initialPaymentAmount: string
  maximumMonthlyPayment: string
  preferentialProgramIds: string[]
  hasOwnedProperty: 'true' | 'false' | 'unknown'
  purchaseGoal: string
  desiredCityId: string
  desiredDistrictId: string
  desiredLayoutIds: string[]
  areaMinimum: string
  areaMaximum: string
  desiredFloor: string
  cardinalDirections: string[]
  comment: string
}

type FieldErrors = Record<string, string>

const emptyFormState: CustomerFormState = {
  firstName: '',
  lastName: '',
  phone: '',
  email: '',
  age: '',
  birthDate: '',
  birthYear: '',
  residenceCityId: '',
  initialPaymentAmount: '',
  maximumMonthlyPayment: '',
  preferentialProgramIds: [],
  hasOwnedProperty: 'unknown',
  purchaseGoal: '',
  desiredCityId: '',
  desiredDistrictId: '',
  desiredLayoutIds: [],
  areaMinimum: '',
  areaMaximum: '',
  desiredFloor: '',
  cardinalDirections: [],
  comment: '',
}

function extractFieldErrors(error: unknown): FieldErrors {
  if (!(error instanceof ApiError) || !error.details) return {}
  if (typeof error.details !== 'object' || Array.isArray(error.details)) {
    return {}
  }
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

function FieldError({
  fieldName,
  errors,
}: {
  fieldName: string
  errors: FieldErrors
}) {
  const message = errors[fieldName]
  if (!message) return null
  return (
    <span className="field-error" id={`${fieldName}-error`}>
      {message}
    </span>
  )
}

function optionalInteger(value: string) {
  if (!value.trim()) return null
  const parsedValue = Number(value)
  return Number.isInteger(parsedValue) ? parsedValue : null
}

function optionalDecimal(value: string) {
  return value.trim() || null
}

function selectedIdentifier(value: string) {
  const parsedValue = Number(value)
  return Number.isInteger(parsedValue) && parsedValue > 0
    ? parsedValue
    : null
}

function buildPayload(formState: CustomerFormState): CustomerWriteRequest {
  return {
    firstName: formState.firstName,
    lastName: formState.lastName,
    phone: formState.phone,
    email: formState.email,
    age: optionalInteger(formState.age),
    birthDate: formState.birthDate || null,
    birthYear: optionalInteger(formState.birthYear),
    residenceCityId: selectedIdentifier(formState.residenceCityId),
    initialPaymentAmount: optionalDecimal(formState.initialPaymentAmount),
    maximumMonthlyPayment: optionalDecimal(formState.maximumMonthlyPayment),
    preferentialProgramIds: formState.preferentialProgramIds.map(Number),
    hasOwnedProperty: formState.hasOwnedProperty === 'unknown'
      ? null
      : formState.hasOwnedProperty === 'true',
    purchaseGoal: formState.purchaseGoal,
    desiredCityId: selectedIdentifier(formState.desiredCityId),
    desiredDistrictId: selectedIdentifier(formState.desiredDistrictId),
    desiredLayoutIds: formState.desiredLayoutIds.map(Number),
    areaMinimum: optionalDecimal(formState.areaMinimum),
    areaMaximum: optionalDecimal(formState.areaMaximum),
    desiredFloor: formState.desiredFloor,
    cardinalDirections: formState.cardinalDirections,
    comment: formState.comment,
  }
}

export function CustomerFormPage() {
  const { customerId } = useParams()
  const isEditing = customerId !== undefined
  const customerIdentifier = Number(customerId ?? 0)
  const hasValidIdentifier = !isEditing
    || (Number.isInteger(customerIdentifier) && customerIdentifier > 0)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const appliedCustomerIdentifierRef = useRef<number | null>(null)
  const sessionQuery = useQuery(sessionQueryOptions)
  const customerQuery = useQuery({
    ...customerDetailQueryOptions(customerIdentifier),
    enabled: isEditing
      && hasValidIdentifier
      && sessionQuery.data?.isAuthenticated === true,
  })
  const [formState, setFormState] = useState<CustomerFormState>(
    emptyFormState,
  )
  const desiredCityIdentifier = selectedIdentifier(formState.desiredCityId)
  const optionsQuery = useQuery({
    ...customerFormOptionsQueryOptions(desiredCityIdentifier),
    enabled: hasValidIdentifier
      && sessionQuery.data?.isAuthenticated === true,
  })
  const mutation = useMutation({
    mutationFn: (payload: CustomerWriteRequest) => (
      isEditing
        ? updateCustomer(customerIdentifier, payload)
        : createCustomer(payload)
    ),
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ['customers'] })
      await queryClient.invalidateQueries({
        queryKey: ['customer', response.id],
      })
      navigate(`/customers/${response.id}`)
    },
  })
  const fieldErrors = extractFieldErrors(mutation.error)
  useDocumentTitle(isEditing ? 'Редактирование клиента' : 'Новый клиент')

  useEffect(() => {
    const customer = customerQuery.data
    if (
      !isEditing
      || !customer
      || appliedCustomerIdentifierRef.current === customer.id
    ) {
      return
    }
    setFormState({
      firstName: customer.firstName,
      lastName: customer.lastName,
      phone: customer.phone,
      email: customer.email,
      age: customer.age?.toString() ?? '',
      birthDate: customer.birthDate ?? '',
      birthYear: customer.birthYear?.toString() ?? '',
      residenceCityId: customer.residenceCityId?.toString() ?? '',
      initialPaymentAmount: customer.initialPaymentAmount ?? '',
      maximumMonthlyPayment: customer.maximumMonthlyPayment ?? '',
      preferentialProgramIds: customer.preferentialPrograms.map(
        (program) => program.id.toString(),
      ),
      hasOwnedProperty: customer.hasOwnedProperty === null
        ? 'unknown'
        : customer.hasOwnedProperty.toString() as 'true' | 'false',
      purchaseGoal: customer.purchaseGoal,
      desiredCityId: customer.desiredCityId?.toString() ?? '',
      desiredDistrictId: customer.desiredDistrictId?.toString() ?? '',
      desiredLayoutIds: customer.desiredLayouts.map(
        (layout) => layout.id.toString(),
      ),
      areaMinimum: customer.areaMinimum ?? '',
      areaMaximum: customer.areaMaximum ?? '',
      desiredFloor: customer.desiredFloor,
      cardinalDirections: customer.cardinalDirections
        .split(',')
        .map((direction) => direction.trim())
        .filter(Boolean),
      comment: customer.comment,
    })
    appliedCustomerIdentifierRef.current = customer.id
  }, [customerQuery.data, isEditing])

  const updateField = <FieldName extends keyof CustomerFormState>(
    fieldName: FieldName,
    value: CustomerFormState[FieldName],
  ) => {
    if (mutation.isError) mutation.reset()
    setFormState((current) => ({ ...current, [fieldName]: value }))
  }

  const updateMultipleChoice = (
    fieldName: 'preferentialProgramIds'
      | 'desiredLayoutIds'
      | 'cardinalDirections',
    value: string,
    isChecked: boolean,
  ) => {
    const currentValues = formState[fieldName]
    updateField(
      fieldName,
      isChecked
        ? [...currentValues, value]
        : currentValues.filter((currentValue) => currentValue !== value),
    )
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    mutation.mutate(buildPayload(formState))
  }

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
    const nextPath = isEditing
      ? `/app/customers/${customerIdentifier}/edit`
      : '/app/customers/new'
    return (
      <EmptyState
        title="Войдите, чтобы работать с клиентами"
        description="Создание и редактирование клиентов доступно после авторизации."
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

  if (isEditing && customerQuery.isLoading) return <PageLoadingState />
  if (isEditing && (customerQuery.isError || !customerQuery.data)) {
    return (
      <ErrorState
        title="Клиент не найден или недоступен"
        onRetry={() => void customerQuery.refetch()}
      />
    )
  }
  if (optionsQuery.isLoading) return <PageLoadingState />
  if (optionsQuery.isError || !optionsQuery.data) {
    return (
      <ErrorState
        title="Не удалось загрузить справочники формы"
        onRetry={() => void optionsQuery.refetch()}
      />
    )
  }

  const options = optionsQuery.data
  const hasTruncatedOptions = Object.values(options.truncated).some(Boolean)
  const legacyFormUrl = isEditing && customerQuery.data
    ? customerQuery.data.legacyEditUrl
    : '/customers/create/'
  const cancelPath = isEditing
    ? `/customers/${customerIdentifier}`
    : '/customers'
  const hasGeneralError = mutation.isError
    && Object.keys(fieldErrors).length === 0

  return (
    <div className="page-stack customer-form-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Работа с клиентами</span>
          <h1>{isEditing ? 'Редактирование клиента' : 'Новый клиент'}</h1>
          <p>
            Обязательное поле только одно — имя. Остальные сведения можно
            добавить сейчас или заполнить позже.
          </p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to={cancelPath}>
            Отмена
          </Link>
          <a className="button button--secondary" href={legacyFormUrl}>
            Django-форма
          </a>
        </div>
      </header>

      {hasTruncatedOptions ? (
        <p className="status-notice" role="status">
          В одном из справочников слишком много значений, поэтому показана
          только первая часть. Полный список доступен в Django-форме.
        </p>
      ) : null}
      {optionsQuery.isFetching ? (
        <p className="customer-form-loading" role="status">
          Обновляем список районов…
        </p>
      ) : null}

      <form className="customer-form" onSubmit={handleSubmit}>
        <section
          className="customer-form-section"
          aria-labelledby="customer-personal-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">01</span>
            <div>
              <h2 id="customer-personal-section">Персональные данные</h2>
              <p>Контакты и сведения для расчёта доступного срока ипотеки.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Имя *
              <input
                name="firstName"
                value={formState.firstName}
                onChange={(event) => updateField('firstName', event.target.value)}
                maxLength={150}
                required
                autoComplete="given-name"
                aria-invalid={Boolean(fieldErrors.firstName)}
                aria-describedby={
                  fieldErrors.firstName ? 'firstName-error' : undefined
                }
              />
              <FieldError fieldName="firstName" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Фамилия
              <input
                name="lastName"
                value={formState.lastName}
                onChange={(event) => updateField('lastName', event.target.value)}
                maxLength={150}
                autoComplete="family-name"
                aria-invalid={Boolean(fieldErrors.lastName)}
                aria-describedby={
                  fieldErrors.lastName ? 'lastName-error' : undefined
                }
              />
              <FieldError fieldName="lastName" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Телефон
              <input
                name="phone"
                type="tel"
                value={formState.phone}
                onChange={(event) => updateField('phone', event.target.value)}
                maxLength={30}
                autoComplete="tel"
                aria-invalid={Boolean(fieldErrors.phone)}
                aria-describedby={
                  fieldErrors.phone ? 'phone-error' : undefined
                }
              />
              <FieldError fieldName="phone" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Email
              <input
                name="email"
                type="email"
                value={formState.email}
                onChange={(event) => updateField('email', event.target.value)}
                autoComplete="email"
                aria-invalid={Boolean(fieldErrors.email)}
                aria-describedby={
                  fieldErrors.email ? 'email-error' : undefined
                }
              />
              <FieldError fieldName="email" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Возраст
              <input
                name="age"
                type="number"
                min="0"
                max="32767"
                value={formState.age}
                onChange={(event) => updateField('age', event.target.value)}
                aria-invalid={Boolean(fieldErrors.age)}
                aria-describedby={
                  fieldErrors.age ? 'age-error age-help' : 'age-help'
                }
              />
              <small id="age-help">
                При указанной дате или годе рождения возраст пересчитается.
              </small>
              <FieldError fieldName="age" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Дата рождения
              <input
                name="birthDate"
                type="date"
                value={formState.birthDate}
                onChange={(event) => updateField('birthDate', event.target.value)}
                aria-invalid={Boolean(fieldErrors.birthDate)}
                aria-describedby={
                  fieldErrors.birthDate ? 'birthDate-error' : undefined
                }
              />
              <FieldError fieldName="birthDate" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Год рождения
              <input
                name="birthYear"
                type="number"
                min="0"
                max="32767"
                value={formState.birthYear}
                onChange={(event) => updateField('birthYear', event.target.value)}
                aria-invalid={Boolean(fieldErrors.birthYear)}
                aria-describedby={
                  fieldErrors.birthYear ? 'birthYear-error' : undefined
                }
              />
              <FieldError fieldName="birthYear" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Город проживания
              <select
                name="residenceCityId"
                value={formState.residenceCityId}
                onChange={(event) => updateField(
                  'residenceCityId',
                  event.target.value,
                )}
                aria-invalid={Boolean(fieldErrors.residenceCityId)}
                aria-describedby={
                  fieldErrors.residenceCityId
                    ? 'residenceCityId-error'
                    : undefined
                }
              >
                <option value="">Не указан</option>
                {options.cities.map((city) => (
                  <option value={city.id} key={city.id}>{city.name}</option>
                ))}
              </select>
              <FieldError fieldName="residenceCityId" errors={fieldErrors} />
            </label>
          </div>
        </section>

        <section
          className="customer-form-section"
          aria-labelledby="customer-finance-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">02</span>
            <div>
              <h2 id="customer-finance-section">Платёжеспособность</h2>
              <p>Данные для предварительной оценки бюджета покупки.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Первоначальный взнос, ₽
              <input
                name="initialPaymentAmount"
                type="number"
                min="0"
                step="0.01"
                value={formState.initialPaymentAmount}
                onChange={(event) => updateField(
                  'initialPaymentAmount',
                  event.target.value,
                )}
                aria-invalid={Boolean(fieldErrors.initialPaymentAmount)}
                aria-describedby={
                  fieldErrors.initialPaymentAmount
                    ? 'initialPaymentAmount-error'
                    : undefined
                }
              />
              <FieldError
                fieldName="initialPaymentAmount"
                errors={fieldErrors}
              />
            </label>
            <label className="form-field">
              Максимальный ежемесячный платёж, ₽
              <input
                name="maximumMonthlyPayment"
                type="number"
                min="0"
                step="0.01"
                value={formState.maximumMonthlyPayment}
                onChange={(event) => updateField(
                  'maximumMonthlyPayment',
                  event.target.value,
                )}
                aria-invalid={Boolean(fieldErrors.maximumMonthlyPayment)}
                aria-describedby={
                  fieldErrors.maximumMonthlyPayment
                    ? 'maximumMonthlyPayment-error'
                    : undefined
                }
              />
              <FieldError
                fieldName="maximumMonthlyPayment"
                errors={fieldErrors}
              />
            </label>
            <fieldset className="form-field form-field--wide customer-choice-field">
              <legend>Доступные льготные программы</legend>
              <div className="customer-choice-grid">
                {options.preferentialPrograms.length > 0
                  ? options.preferentialPrograms.map((program) => (
                    <label key={program.id}>
                      <input
                        type="checkbox"
                        value={program.id}
                        checked={formState.preferentialProgramIds.includes(
                          program.id.toString(),
                        )}
                        onChange={(event) => updateMultipleChoice(
                          'preferentialProgramIds',
                          event.target.value,
                          event.target.checked,
                        )}
                      />
                      <span>{program.name}</span>
                    </label>
                  ))
                  : <p>Нет доступных программ</p>}
              </div>
              <FieldError
                fieldName="preferentialProgramIds"
                errors={fieldErrors}
              />
            </fieldset>
            <fieldset className="form-field form-field--wide customer-choice-field">
              <legend>Наличие недвижимости в собственности</legend>
              <div className="customer-radio-row">
                {[
                  ['true', 'Да'],
                  ['false', 'Нет'],
                  ['unknown', 'Не указано'],
                ].map(([value, label]) => (
                  <label key={value}>
                    <input
                      type="radio"
                      name="hasOwnedProperty"
                      value={value}
                      checked={formState.hasOwnedProperty === value}
                      onChange={() => updateField(
                        'hasOwnedProperty',
                        value as CustomerFormState['hasOwnedProperty'],
                      )}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
              <FieldError fieldName="hasOwnedProperty" errors={fieldErrors} />
            </fieldset>
          </div>
        </section>

        <section
          className="customer-form-section"
          aria-labelledby="customer-preferences-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">03</span>
            <div>
              <h2 id="customer-preferences-section">
                Параметры недвижимости
              </h2>
              <p>Критерии для будущего подбора подходящих объектов.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Цель покупки
              <select
                name="purchaseGoal"
                value={formState.purchaseGoal}
                onChange={(event) => updateField(
                  'purchaseGoal',
                  event.target.value,
                )}
              >
                <option value="">Не указана</option>
                {options.purchaseGoals.map((goal) => (
                  <option value={goal.value} key={goal.value}>
                    {goal.label}
                  </option>
                ))}
              </select>
              <FieldError fieldName="purchaseGoal" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Желаемый город покупки
              <select
                name="desiredCityId"
                value={formState.desiredCityId}
                onChange={(event) => {
                  if (mutation.isError) mutation.reset()
                  setFormState((current) => ({
                    ...current,
                    desiredCityId: event.target.value,
                    desiredDistrictId: '',
                  }))
                }}
                aria-invalid={Boolean(fieldErrors.desiredCityId)}
                aria-describedby={
                  fieldErrors.desiredCityId ? 'desiredCityId-error' : undefined
                }
              >
                <option value="">Не указан</option>
                {options.cities.map((city) => (
                  <option value={city.id} key={city.id}>{city.name}</option>
                ))}
              </select>
              <FieldError fieldName="desiredCityId" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Желаемый район
              <select
                name="desiredDistrictId"
                value={formState.desiredDistrictId}
                disabled={!desiredCityIdentifier || optionsQuery.isFetching}
                onChange={(event) => updateField(
                  'desiredDistrictId',
                  event.target.value,
                )}
                aria-invalid={Boolean(fieldErrors.desiredDistrictId)}
                aria-describedby={
                  fieldErrors.desiredDistrictId
                    ? 'desiredDistrictId-error'
                    : undefined
                }
              >
                <option value="">Не указан</option>
                {options.districts.map((district) => (
                  <option value={district.id} key={district.id}>
                    {district.name}
                  </option>
                ))}
              </select>
              <FieldError fieldName="desiredDistrictId" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Этаж
              <input
                name="desiredFloor"
                value={formState.desiredFloor}
                onChange={(event) => updateField(
                  'desiredFloor',
                  event.target.value,
                )}
                maxLength={100}
                placeholder="Например, не первый или 5–12"
                aria-invalid={Boolean(fieldErrors.desiredFloor)}
                aria-describedby={
                  fieldErrors.desiredFloor ? 'desiredFloor-error' : undefined
                }
              />
              <FieldError fieldName="desiredFloor" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Площадь от, м²
              <input
                name="areaMinimum"
                type="number"
                min="0"
                step="0.01"
                value={formState.areaMinimum}
                onChange={(event) => updateField(
                  'areaMinimum',
                  event.target.value,
                )}
                aria-invalid={Boolean(fieldErrors.areaMinimum)}
                aria-describedby={
                  fieldErrors.areaMinimum ? 'areaMinimum-error' : undefined
                }
              />
              <FieldError fieldName="areaMinimum" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Площадь до, м²
              <input
                name="areaMaximum"
                type="number"
                min="0"
                step="0.01"
                value={formState.areaMaximum}
                onChange={(event) => updateField(
                  'areaMaximum',
                  event.target.value,
                )}
                aria-invalid={Boolean(fieldErrors.areaMaximum)}
                aria-describedby={
                  fieldErrors.areaMaximum ? 'areaMaximum-error' : undefined
                }
              />
              <FieldError fieldName="areaMaximum" errors={fieldErrors} />
            </label>
            <fieldset className="form-field form-field--wide customer-choice-field">
              <legend>Планировки</legend>
              <div className="customer-choice-grid">
                {options.layouts.length > 0
                  ? options.layouts.map((layout) => (
                    <label key={layout.id}>
                      <input
                        type="checkbox"
                        value={layout.id}
                        checked={formState.desiredLayoutIds.includes(
                          layout.id.toString(),
                        )}
                        onChange={(event) => updateMultipleChoice(
                          'desiredLayoutIds',
                          event.target.value,
                          event.target.checked,
                        )}
                      />
                      <span>{layout.name}</span>
                    </label>
                  ))
                  : <p>Нет доступных планировок</p>}
              </div>
              <FieldError fieldName="desiredLayoutIds" errors={fieldErrors} />
            </fieldset>
            <fieldset className="form-field form-field--wide customer-choice-field">
              <legend>Стороны света</legend>
              <div className="customer-choice-grid customer-choice-grid--compact">
                {options.cardinalDirections.map((direction) => (
                  <label key={direction.value}>
                    <input
                      type="checkbox"
                      value={direction.value}
                      checked={formState.cardinalDirections.includes(
                        direction.value,
                      )}
                      onChange={(event) => updateMultipleChoice(
                        'cardinalDirections',
                        event.target.value,
                        event.target.checked,
                      )}
                    />
                    <span>{direction.label}</span>
                  </label>
                ))}
              </div>
              <FieldError
                fieldName="cardinalDirections"
                errors={fieldErrors}
              />
            </fieldset>
            <label className="form-field form-field--wide">
              Комментарий
              <textarea
                name="comment"
                rows={5}
                value={formState.comment}
                onChange={(event) => updateField('comment', event.target.value)}
                aria-invalid={Boolean(fieldErrors.comment)}
                aria-describedby={
                  fieldErrors.comment ? 'comment-error' : undefined
                }
              />
              <FieldError fieldName="comment" errors={fieldErrors} />
            </label>
          </div>
        </section>

        {fieldErrors.nonFieldErrors ? (
          <p className="form-error" role="alert">
            {fieldErrors.nonFieldErrors}
          </p>
        ) : null}
        {hasGeneralError ? (
          <p className="form-error" role="alert">
            Не удалось сохранить клиента. Проверьте данные и повторите попытку.
          </p>
        ) : null}

        <div className="customer-form-actions">
          <button
            className="button button--primary"
            type="submit"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? 'Сохраняем…' : 'Сохранить клиента'}
          </button>
          <Link className="button button--secondary" to={cancelPath}>
            Отмена
          </Link>
        </div>
      </form>
    </div>
  )
}
