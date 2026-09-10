import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  companyGroupDetailQueryOptions,
  createCompanyGroup,
  sessionQueryOptions,
  updateCompanyGroup,
} from '@/api/queries'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type FieldErrors = Record<string, string>

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

export function CompanyGroupFormPage() {
  const { companyGroupId } = useParams()
  const isEditing = companyGroupId !== undefined
  const companyGroupIdentifier = Number(companyGroupId ?? 0)
  const hasValidIdentifier = !isEditing || (
    Number.isInteger(companyGroupIdentifier) && companyGroupIdentifier > 0
  )
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const initializedCompanyGroupRef = useRef<number | null>(null)
  const [name, setName] = useState('')
  const sessionQuery = useQuery(sessionQueryOptions)
  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  const companyGroupQuery = useQuery({
    ...companyGroupDetailQueryOptions(companyGroupIdentifier),
    enabled: isEditing && hasValidIdentifier && canManageCatalogs,
  })
  const mutation = useMutation({
    mutationFn: (submittedName: string) => (
      isEditing
        ? updateCompanyGroup(companyGroupIdentifier, submittedName)
        : createCompanyGroup(submittedName)
    ),
    onSuccess: async (companyGroup) => {
      queryClient.setQueryData(
        ['company-group', companyGroup.id],
        companyGroup,
      )
      await queryClient.invalidateQueries({ queryKey: ['company-groups'] })
      navigate('/company-groups')
    },
  })
  const fieldErrors = extractFieldErrors(mutation.error)
  useDocumentTitle(
    isEditing ? 'Редактирование группы компаний' : 'Новая группа компаний',
  )

  useEffect(() => {
    const companyGroup = companyGroupQuery.data
    if (
      !isEditing
      || !companyGroup
      || initializedCompanyGroupRef.current === companyGroup.id
    ) {
      return
    }
    setName(companyGroup.name)
    initializedCompanyGroupRef.current = companyGroup.id
  }, [companyGroupQuery.data, isEditing])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    mutation.mutate(name.trim())
  }

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Группа компаний не найдена"
        description="Проверьте адрес или вернитесь к списку."
        action={(
          <Link className="button button--secondary" to="/company-groups">
            К списку
          </Link>
        )}
      />
    )
  }
  if (sessionQuery.isLoading) return <PageLoadingState />
  if (!sessionQuery.data?.isAuthenticated) {
    const nextPath = isEditing
      ? `/app/company-groups/${companyGroupIdentifier}/edit`
      : '/app/company-groups/new'
    return (
      <EmptyState
        title="Войдите для управления справочником"
        description="Создание и редактирование доступно модераторам каталога."
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
  if (!canManageCatalogs) {
    return (
      <EmptyState
        title="Недостаточно прав"
        description="Изменять группы компаний могут модераторы каталога."
        action={(
          <Link className="button button--secondary" to="/company-groups">
            К списку
          </Link>
        )}
      />
    )
  }
  if (isEditing && companyGroupQuery.isLoading) return <PageLoadingState />
  if (isEditing && (
    companyGroupQuery.isError || !companyGroupQuery.data
  )) {
    return (
      <ErrorState
        title="Группа компаний не найдена или недоступна"
        onRetry={() => void companyGroupQuery.refetch()}
      />
    )
  }

  const legacyFormUrl = isEditing && companyGroupQuery.data
    ? companyGroupQuery.data.legacyEditUrl
    : '/property/company-groups/create/'
  const hasGeneralError = mutation.isError && (
    Object.keys(fieldErrors).length === 0
    || Boolean(fieldErrors.non_field_errors)
    || Boolean(fieldErrors.detail)
  )

  return (
    <div className="page-stack company-group-form-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Недвижимость</span>
          <h1>
            {isEditing
              ? 'Редактирование группы компаний'
              : 'Новая группа компаний'}
          </h1>
          <p>
            Название используется в карточках и фильтрах застройщиков.
          </p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to="/company-groups">
            Отмена
          </Link>
          <a className="button button--secondary" href={legacyFormUrl}>
            Django-форма
          </a>
        </div>
      </header>

      <form
        className="customer-form catalog-entry-form"
        onSubmit={handleSubmit}
      >
        <section
          className="customer-form-section catalog-entry-form__section"
          aria-labelledby="company-group-main-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">01</span>
            <div>
              <h2 id="company-group-main-section">Основные данные</h2>
              <p>Укажите уникальное полное название группы.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Название *
              <input
                name="name"
                value={name}
                onChange={(event) => {
                  setName(event.target.value)
                  if (mutation.isError) mutation.reset()
                }}
                maxLength={255}
                required
                autoFocus
                autoComplete="organization"
                aria-invalid={Boolean(fieldErrors.name)}
                aria-describedby={fieldErrors.name ? 'name-error' : undefined}
              />
              {fieldErrors.name ? (
                <span className="field-error" id="name-error">
                  {fieldErrors.name}
                </span>
              ) : null}
            </label>
          </div>
        </section>

        {hasGeneralError ? (
          <p className="form-error" role="alert">
            {fieldErrors.non_field_errors
              || fieldErrors.detail
              || 'Не удалось сохранить группу. Повторите попытку.'}
          </p>
        ) : null}
        <div className="customer-form-actions">
          <Link className="button button--secondary" to="/company-groups">
            Отмена
          </Link>
          <button
            className="button button--primary"
            type="submit"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? 'Сохраняем…' : 'Сохранить'}
          </button>
        </div>
      </form>
    </div>
  )
}
