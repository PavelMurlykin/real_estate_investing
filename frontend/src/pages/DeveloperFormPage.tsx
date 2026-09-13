import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  createDeveloper,
  developerDetailQueryOptions,
  developerOptionsQueryOptions,
  sessionQueryOptions,
  updateDeveloper,
} from '@/api/queries'
import type { DeveloperWriteRequest } from '@/api/schemas'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type DeveloperFormState = {
  name: string
  companyGroupId: string
  regionIds: string[]
  legalAddress: string
  actualAddress: string
  taxpayerIdentificationNumber: string
  taxRegistrationReasonCode: string
  primaryStateRegistrationNumber: string
  description: string
  isActive: boolean
}

type FieldErrors = Record<string, string>

const emptyFormState: DeveloperFormState = {
  name: '',
  companyGroupId: '',
  regionIds: [],
  legalAddress: '',
  actualAddress: '',
  taxpayerIdentificationNumber: '',
  taxRegistrationReasonCode: '',
  primaryStateRegistrationNumber: '',
  description: '',
  isActive: true,
}

function selectedIdentifier(value: string) {
  const identifier = Number(value)
  return Number.isInteger(identifier) && identifier > 0 ? identifier : null
}

function nullableText(value: string) {
  const normalizedValue = value.trim()
  return normalizedValue || null
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

export function DeveloperFormPage() {
  const { developerId } = useParams()
  const isEditing = developerId !== undefined
  const developerIdentifier = Number(developerId ?? 0)
  const hasValidIdentifier = !isEditing || (
    Number.isInteger(developerIdentifier) && developerIdentifier > 0
  )
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const initializedDeveloperRef = useRef<number | null>(null)
  const [formState, setFormState] = useState(emptyFormState)
  const sessionQuery = useQuery(sessionQueryOptions)
  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  const developerQuery = useQuery({
    ...developerDetailQueryOptions(developerIdentifier),
    enabled: isEditing && hasValidIdentifier && canManageCatalogs,
  })
  const optionsQuery = useQuery({
    ...developerOptionsQueryOptions,
    enabled: canManageCatalogs,
  })
  const mutation = useMutation({
    mutationFn: (payload: DeveloperWriteRequest) => (
      isEditing
        ? updateDeveloper(developerIdentifier, payload)
        : createDeveloper(payload)
    ),
    onSuccess: async (developer) => {
      queryClient.setQueryData(['developer', developer.id], developer)
      await queryClient.invalidateQueries({ queryKey: ['developers'] })
      navigate('/developers')
    },
  })
  const fieldErrors = extractFieldErrors(mutation.error)
  useDocumentTitle(isEditing ? 'Редактирование застройщика' : 'Новый застройщик')

  useEffect(() => {
    const developer = developerQuery.data
    if (
      !isEditing
      || !developer
      || initializedDeveloperRef.current === developer.id
    ) {
      return
    }
    setFormState({
      name: developer.name,
      companyGroupId: developer.companyGroup?.id.toString() ?? '',
      regionIds: developer.regions.map((region) => region.id.toString()),
      legalAddress: developer.legalAddress ?? '',
      actualAddress: developer.actualAddress ?? '',
      taxpayerIdentificationNumber:
        developer.taxpayerIdentificationNumber ?? '',
      taxRegistrationReasonCode: developer.taxRegistrationReasonCode ?? '',
      primaryStateRegistrationNumber:
        developer.primaryStateRegistrationNumber ?? '',
      description: developer.description ?? '',
      isActive: developer.isActive,
    })
    initializedDeveloperRef.current = developer.id
  }, [developerQuery.data, isEditing])

  const updateField = <FieldName extends keyof DeveloperFormState>(
    fieldName: FieldName,
    value: DeveloperFormState[FieldName],
  ) => {
    setFormState((currentState) => ({
      ...currentState,
      [fieldName]: value,
    }))
    if (mutation.isError) mutation.reset()
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    mutation.mutate({
      name: formState.name.trim(),
      companyGroupId: selectedIdentifier(formState.companyGroupId),
      regionIds: formState.regionIds
        .map(selectedIdentifier)
        .filter((identifier): identifier is number => identifier !== null),
      legalAddress: nullableText(formState.legalAddress),
      actualAddress: nullableText(formState.actualAddress),
      taxpayerIdentificationNumber: nullableText(
        formState.taxpayerIdentificationNumber,
      ),
      taxRegistrationReasonCode: nullableText(
        formState.taxRegistrationReasonCode,
      ),
      primaryStateRegistrationNumber: nullableText(
        formState.primaryStateRegistrationNumber,
      ),
      description: nullableText(formState.description),
      isActive: formState.isActive,
    })
  }

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Застройщик не найден"
        description="Проверьте адрес или вернитесь к списку."
        action={(
          <Link className="button button--secondary" to="/developers">
            К списку
          </Link>
        )}
      />
    )
  }
  if (sessionQuery.isLoading) return <PageLoadingState />
  if (!sessionQuery.data?.isAuthenticated) {
    const nextPath = isEditing
      ? `/app/developers/${developerIdentifier}/edit`
      : '/app/developers/new'
    return (
      <EmptyState
        title="Войдите для управления застройщиками"
        description="Полные данные и изменение справочника доступны модераторам."
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
        description="Изменять застройщиков могут модераторы каталога."
        action={(
          <Link className="button button--secondary" to="/developers">
            К списку
          </Link>
        )}
      />
    )
  }
  if (
    optionsQuery.isLoading
    || (isEditing && developerQuery.isLoading)
  ) {
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
  if (isEditing && (developerQuery.isError || !developerQuery.data)) {
    return (
      <ErrorState
        title="Застройщик не найден или недоступен"
        onRetry={() => void developerQuery.refetch()}
      />
    )
  }

  const legacyFormUrl = isEditing && developerQuery.data
    ? developerQuery.data.legacyEditUrl
    : '/property/developers/create/'
  const hasGeneralError = mutation.isError && (
    Object.keys(fieldErrors).length === 0
    || Boolean(fieldErrors.non_field_errors)
    || Boolean(fieldErrors.detail)
  )
  const optionsAreTruncated = (
    optionsQuery.data.truncated.companyGroups
    || optionsQuery.data.truncated.regions
  )

  return (
    <div className="page-stack developer-form-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Недвижимость</span>
          <h1>{isEditing ? 'Редактирование застройщика' : 'Новый застройщик'}</h1>
          <p>Основные сведения, география работы и реквизиты компании.</p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to="/developers">
            Отмена
          </Link>
          <a className="button button--secondary" href={legacyFormUrl}>
            Django-форма
          </a>
        </div>
      </header>

      <form className="customer-form developer-form" onSubmit={handleSubmit}>
        <section
          className="customer-form-section"
          aria-labelledby="developer-main-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">01</span>
            <div>
              <h2 id="developer-main-section">Основные данные</h2>
              <p>Название, группа компаний и регионы работы.</p>
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
                aria-invalid={Boolean(fieldErrors.name)}
                aria-describedby={fieldErrors.name ? 'name-error' : undefined}
              />
              <FieldError fieldName="name" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Группа компаний
              <select
                name="companyGroupId"
                value={formState.companyGroupId}
                onChange={(event) => updateField(
                  'companyGroupId',
                  event.target.value,
                )}
                aria-invalid={Boolean(fieldErrors.companyGroupId)}
                aria-describedby={fieldErrors.companyGroupId
                  ? 'companyGroupId-error'
                  : undefined}
              >
                <option value="">Без группы компаний</option>
                {optionsQuery.data.companyGroups.map((companyGroup) => (
                  <option value={companyGroup.id} key={companyGroup.id}>
                    {companyGroup.name}
                  </option>
                ))}
              </select>
              <FieldError fieldName="companyGroupId" errors={fieldErrors} />
            </label>
            <div className="form-field form-field--wide">
              <label htmlFor="developer-region-ids">Регионы</label>
              <select
                id="developer-region-ids"
                className="developer-region-select"
                name="regionIds"
                multiple
                value={formState.regionIds}
                onChange={(event) => updateField(
                  'regionIds',
                  Array.from(
                    event.target.selectedOptions,
                    (option) => option.value,
                  ),
                )}
                aria-invalid={Boolean(fieldErrors.regionIds)}
                aria-describedby={fieldErrors.regionIds
                  ? 'regionIds-error'
                  : 'developer-regions-hint'}
              >
                {optionsQuery.data.regions.map((region) => (
                  <option value={region.id} key={region.id}>{region.name}</option>
                ))}
              </select>
              <small id="developer-regions-hint">
                Для выбора нескольких регионов используйте Ctrl или Cmd.
              </small>
              <FieldError fieldName="regionIds" errors={fieldErrors} />
            </div>
            {optionsAreTruncated ? (
              <p className="form-error form-field--wide" role="alert">
                Справочник слишком велик и показан не полностью. Для выбора
                отсутствующей записи используйте сохранённую Django-форму.
              </p>
            ) : null}
          </div>
        </section>

        <section
          className="customer-form-section"
          aria-labelledby="developer-address-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">02</span>
            <div>
              <h2 id="developer-address-section">Адреса и реквизиты</h2>
              <p>Служебные данные доступны только модераторам каталога.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Юридический адрес
              <textarea
                name="legalAddress"
                value={formState.legalAddress}
                onChange={(event) => updateField(
                  'legalAddress',
                  event.target.value,
                )}
                aria-invalid={Boolean(fieldErrors.legalAddress)}
                aria-describedby={fieldErrors.legalAddress
                  ? 'legalAddress-error'
                  : undefined}
              />
              <FieldError fieldName="legalAddress" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Фактический адрес
              <textarea
                name="actualAddress"
                value={formState.actualAddress}
                onChange={(event) => updateField(
                  'actualAddress',
                  event.target.value,
                )}
                aria-invalid={Boolean(fieldErrors.actualAddress)}
                aria-describedby={fieldErrors.actualAddress
                  ? 'actualAddress-error'
                  : undefined}
              />
              <FieldError fieldName="actualAddress" errors={fieldErrors} />
            </label>
            <label className="form-field">
              ИНН
              <input
                name="taxpayerIdentificationNumber"
                value={formState.taxpayerIdentificationNumber}
                onChange={(event) => updateField(
                  'taxpayerIdentificationNumber',
                  event.target.value,
                )}
                maxLength={12}
                inputMode="numeric"
                aria-invalid={Boolean(
                  fieldErrors.taxpayerIdentificationNumber,
                )}
                aria-describedby={fieldErrors.taxpayerIdentificationNumber
                  ? 'taxpayerIdentificationNumber-error'
                  : undefined}
              />
              <FieldError
                fieldName="taxpayerIdentificationNumber"
                errors={fieldErrors}
              />
            </label>
            <label className="form-field">
              КПП
              <input
                name="taxRegistrationReasonCode"
                value={formState.taxRegistrationReasonCode}
                onChange={(event) => updateField(
                  'taxRegistrationReasonCode',
                  event.target.value,
                )}
                maxLength={9}
                inputMode="numeric"
                aria-invalid={Boolean(fieldErrors.taxRegistrationReasonCode)}
                aria-describedby={fieldErrors.taxRegistrationReasonCode
                  ? 'taxRegistrationReasonCode-error'
                  : undefined}
              />
              <FieldError
                fieldName="taxRegistrationReasonCode"
                errors={fieldErrors}
              />
            </label>
            <label className="form-field">
              ОГРН
              <input
                name="primaryStateRegistrationNumber"
                value={formState.primaryStateRegistrationNumber}
                onChange={(event) => updateField(
                  'primaryStateRegistrationNumber',
                  event.target.value,
                )}
                maxLength={15}
                inputMode="numeric"
                aria-invalid={Boolean(
                  fieldErrors.primaryStateRegistrationNumber,
                )}
                aria-describedby={fieldErrors.primaryStateRegistrationNumber
                  ? 'primaryStateRegistrationNumber-error'
                  : undefined}
              />
              <FieldError
                fieldName="primaryStateRegistrationNumber"
                errors={fieldErrors}
              />
            </label>
          </div>
        </section>

        <section
          className="customer-form-section"
          aria-labelledby="developer-description-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">03</span>
            <div>
              <h2 id="developer-description-section">Описание и статус</h2>
              <p>Дополнительный контекст и доступность записи в каталогах.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field form-field--wide">
              Описание
              <textarea
                name="description"
                value={formState.description}
                onChange={(event) => updateField(
                  'description',
                  event.target.value,
                )}
                aria-invalid={Boolean(fieldErrors.description)}
                aria-describedby={fieldErrors.description
                  ? 'description-error'
                  : undefined}
              />
              <FieldError fieldName="description" errors={fieldErrors} />
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
                <strong>Активный застройщик</strong>
                <small>Запись доступна для выбора в рабочих формах.</small>
              </span>
            </label>
          </div>
        </section>

        {hasGeneralError ? (
          <p className="form-error" role="alert">
            {fieldErrors.non_field_errors
              || fieldErrors.detail
              || 'Не удалось сохранить застройщика. Повторите попытку.'}
          </p>
        ) : null}
        <div className="customer-form-actions">
          <Link className="button button--secondary" to="/developers">
            Отмена
          </Link>
          <button
            className="button button--primary"
            type="submit"
            disabled={mutation.isPending}
          >
            {mutation.isPending
              ? 'Сохраняем…'
              : isEditing ? 'Сохранить изменения' : 'Создать застройщика'}
          </button>
        </div>
      </form>
    </div>
  )
}
