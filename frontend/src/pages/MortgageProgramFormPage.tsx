import { Notice } from '@/shared/ui/Notice'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  createMortgageProgram,
  mortgageProgramDetailQueryOptions,
  mortgageProgramOptionsQueryOptions,
  sessionQueryOptions,
  updateMortgageProgram,
} from '@/api/queries'
import type { MortgageProgramWriteRequest } from '@/api/schemas'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type RegionalLimit = {
  key: string
  regionId: string
  creditLimit: string
  isActive: boolean
}
type FormState = {
  name: string
  condition: string
  creditLimit: string
  isPreferential: boolean
  isActive: boolean
  regionalCreditLimits: RegionalLimit[]
}
type Errors = {
  name?: string
  condition?: string
  creditLimit?: string
  limits: Record<string, { regionId?: string; creditLimit?: string }>
}

const emptyState: FormState = {
  name: '',
  condition: '',
  creditLimit: '',
  isPreferential: false,
  isActive: true,
  regionalCreditLimits: [],
}
const emptyErrors: Errors = { limits: {} }

function normalizeDecimal(value: string) {
  return value.trim().replace(',', '.')
}

function creditLimitError(value: string, required = false) {
  if (!value.trim()) return required ? 'Укажите кредитный лимит.' : undefined
  const numericValue = Number(normalizeDecimal(value))
  if (!Number.isFinite(numericValue) || numericValue < 0) {
    return 'Лимит должен быть неотрицательным числом.'
  }
  if (numericValue > 9_999_999_999_999.99) {
    return 'Лимит превышает допустимое значение.'
  }
  return undefined
}

function firstNestedError(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = firstNestedError(item)
      if (message) return message
    }
  } else if (value && typeof value === 'object') {
    for (const item of Object.values(value)) {
      const message = firstNestedError(item)
      if (message) return message
    }
  }
  return null
}

function apiErrorMessage(error: unknown) {
  if (!(error instanceof ApiError)) return null
  if (!error.details || typeof error.details !== 'object') return error.message
  return firstNestedError(error.details) ?? error.message
}

export function MortgageProgramFormPage() {
  const { mortgageProgramId } = useParams()
  const isEditing = mortgageProgramId !== undefined
  const identifier = Number(mortgageProgramId ?? 0)
  const hasValidIdentifier = !isEditing
    || (Number.isInteger(identifier) && identifier > 0)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const initializedRef = useRef<number | null>(null)
  const nextKeyRef = useRef(0)
  const [formState, setFormState] = useState<FormState>(emptyState)
  const [errors, setErrors] = useState<Errors>(emptyErrors)
  const sessionQuery = useQuery(sessionQueryOptions)
  const canManage = sessionQuery.data?.capabilities.manageCatalogs === true
  const detailQuery = useQuery({
    ...mortgageProgramDetailQueryOptions(identifier),
    enabled: isEditing && hasValidIdentifier && canManage,
  })
  const optionsQuery = useQuery({
    ...mortgageProgramOptionsQueryOptions,
    enabled: canManage,
  })
  const mutation = useMutation({
    mutationFn: (payload: MortgageProgramWriteRequest) => isEditing
      ? updateMortgageProgram(identifier, payload)
      : createMortgageProgram(payload),
    onSuccess: async (program) => {
      queryClient.setQueryData(['mortgage-program', program.id], program)
      await queryClient.invalidateQueries({ queryKey: ['mortgage-programs'] })
      navigate(`/mortgage-programs/${program.id}`)
    },
  })
  useDocumentTitle(isEditing
    ? 'Редактирование ипотечной программы'
    : 'Новая ипотечная программа')

  useEffect(() => {
    const program = detailQuery.data
    if (!program || initializedRef.current === program.id) return
    setFormState({
      name: program.name,
      condition: program.condition,
      creditLimit: program.creditLimit ?? '',
      isPreferential: program.isPreferential,
      isActive: program.isActive,
      regionalCreditLimits: program.regionalCreditLimits.map((limit) => ({
        key: `limit-${limit.id}`,
        regionId: String(limit.regionId),
        creditLimit: limit.creditLimit,
        isActive: limit.isActive,
      })),
    })
    initializedRef.current = program.id
  }, [detailQuery.data])

  const changed = () => {
    setErrors(emptyErrors)
    if (mutation.isError) mutation.reset()
  }
  const setField = <Field extends keyof Omit<
    FormState,
    'regionalCreditLimits'
  >>(field: Field, value: FormState[Field]) => {
    setFormState((current) => ({ ...current, [field]: value }))
    changed()
  }
  const addLimit = () => {
    const key = `new-limit-${nextKeyRef.current++}`
    setFormState((current) => ({
      ...current,
      regionalCreditLimits: [
        ...current.regionalCreditLimits,
        { key, regionId: '', creditLimit: '', isActive: true },
      ],
    }))
    changed()
  }
  const updateLimit = (
    key: string,
    field: keyof Omit<RegionalLimit, 'key'>,
    value: string | boolean,
  ) => {
    setFormState((current) => ({
      ...current,
      regionalCreditLimits: current.regionalCreditLimits.map((limit) => (
        limit.key === key ? { ...limit, [field]: value } : limit
      )),
    }))
    changed()
  }
  const removeLimit = (key: string) => {
    setFormState((current) => ({
      ...current,
      regionalCreditLimits: current.regionalCreditLimits.filter(
        (limit) => limit.key !== key,
      ),
    }))
    changed()
  }
  const validate = () => {
    const nextErrors: Errors = { limits: {} }
    if (!formState.name.trim()) nextErrors.name = 'Укажите название программы.'
    if (!formState.condition.trim()) {
      nextErrors.condition = 'Опишите условия программы.'
    }
    nextErrors.creditLimit = creditLimitError(formState.creditLimit)
    const regions = new Set<string>()
    for (const limit of formState.regionalCreditLimits) {
      const row: { regionId?: string; creditLimit?: string } = {}
      if (!limit.regionId) row.regionId = 'Выберите регион.'
      else if (regions.has(limit.regionId)) {
        row.regionId = 'Этот регион уже добавлен.'
      } else regions.add(limit.regionId)
      row.creditLimit = creditLimitError(limit.creditLimit, true)
      if (row.regionId || row.creditLimit) nextErrors.limits[limit.key] = row
    }
    setErrors(nextErrors)
    return !nextErrors.name
      && !nextErrors.condition
      && !nextErrors.creditLimit
      && Object.keys(nextErrors.limits).length === 0
  }

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!validate()) return
    mutation.mutate({
      name: formState.name.trim(),
      condition: formState.condition.trim(),
      creditLimit: formState.creditLimit.trim()
        ? normalizeDecimal(formState.creditLimit)
        : null,
      isPreferential: formState.isPreferential,
      isActive: formState.isActive,
      regionalCreditLimits: formState.regionalCreditLimits.map((limit) => ({
        regionId: Number(limit.regionId),
        creditLimit: normalizeDecimal(limit.creditLimit),
        isActive: limit.isActive,
      })),
    })
  }

  const backLink = (
    <Link className="button button--secondary" to="/mortgage-programs">
      К списку
    </Link>
  )
  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Ипотечная программа не найдена"
        description="Проверьте адрес или вернитесь к списку."
        action={backLink}
      />
    )
  }
  if (sessionQuery.isLoading) return <PageLoadingState />
  if (!sessionQuery.data?.isAuthenticated) {
    const nextPath = isEditing
      ? `/app/mortgage-programs/${identifier}/edit`
      : '/app/mortgage-programs/new'
    return (
      <EmptyState
        title="Войдите для управления программами"
        description="Изменение ипотечного справочника доступно модераторам."
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
        title="Не удалось загрузить список регионов"
        onRetry={() => void optionsQuery.refetch()}
      />
    )
  }
  if (isEditing && (detailQuery.isError || !detailQuery.data)) {
    return (
      <ErrorState
        title="Ипотечная программа не найдена или недоступна"
        onRetry={() => void detailQuery.refetch()}
      />
    )
  }

  const regions = [...optionsQuery.data.regions]
  for (const limit of detailQuery.data?.regionalCreditLimits ?? []) {
    if (!regions.some((region) => region.id === limit.regionId)) {
      regions.push({ id: limit.regionId, name: limit.regionName })
    }
  }
  regions.sort((left, right) => left.name.localeCompare(right.name, 'ru'))
  return (
    <div className="page-stack mortgage-program-form-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Ипотечный справочник</span>
          <h1>{isEditing
            ? 'Редактирование ипотечной программы'
            : 'Новая ипотечная программа'}</h1>
          <p>Общие условия и региональные лимиты.</p>
        </div>
        <div className="page-header__actions">
          {backLink}
        </div>
      </header>
      <form className="customer-form mortgage-program-form" onSubmit={submit} noValidate>
        <section className="customer-form-section" aria-labelledby="program-main">
          <div className="customer-form-section__heading">
            <span aria-hidden="true">01</span>
            <div>
              <h2 id="program-main">Основные данные</h2>
              <p>Название, тип программы и федеральные условия.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Название *
              <input
                name="name"
                value={formState.name}
                onChange={(event) => setField('name', event.target.value)}
                maxLength={255}
                required
                autoFocus
                aria-invalid={Boolean(errors.name)}
                aria-describedby="program-name-error"
              />
              {errors.name ? (
                <span className="field-error" id="program-name-error">
                  {errors.name}
                </span>
              ) : null}
            </label>
            <label className="form-field">
              Федеральный лимит, ₽
              <input
                name="creditLimit"
                type="number"
                min="0"
                max="9999999999999.99"
                step="0.01"
                inputMode="decimal"
                value={formState.creditLimit}
                onChange={(event) => setField(
                  'creditLimit',
                  event.target.value,
                )}
                aria-invalid={Boolean(errors.creditLimit)}
                aria-describedby="program-limit-hint program-limit-error"
              />
              <small id="program-limit-hint">
                Оставьте пустым, если единого лимита нет.
              </small>
              {errors.creditLimit ? (
                <span className="field-error" id="program-limit-error">
                  {errors.creditLimit}
                </span>
              ) : null}
            </label>
            <label className="form-field form-field--wide">
              Условия *
              <textarea
                name="condition"
                rows={5}
                value={formState.condition}
                onChange={(event) => setField('condition', event.target.value)}
                required
                aria-invalid={Boolean(errors.condition)}
                aria-describedby="program-condition-error"
              />
              {errors.condition ? (
                <span className="field-error" id="program-condition-error">
                  {errors.condition}
                </span>
              ) : null}
            </label>
            <label className="developer-active-field">
              <input
                type="checkbox"
                checked={formState.isPreferential}
                onChange={(event) => setField(
                  'isPreferential',
                  event.target.checked,
                )}
              />
              <span>
                <strong>Льготная программа</strong>
                <small>Использует льготные условия кредитования.</small>
              </span>
            </label>
            <label className="developer-active-field">
              <input
                type="checkbox"
                checked={formState.isActive}
                onChange={(event) => setField('isActive', event.target.checked)}
              />
              <span>
                <strong>Активная программа</strong>
                <small>Доступна в рабочих формах и расчётах.</small>
              </span>
            </label>
          </div>
        </section>
        <section className="customer-form-section" aria-labelledby="program-limits">
          <div className="customer-form-section__heading">
            <span aria-hidden="true">02</span>
            <div>
              <h2 id="program-limits">Региональные лимиты</h2>
              <p>Лимиты для регионов, где они отличаются от федерального.</p>
            </div>
          </div>
          <div className="form-section-actions">
            <button
              className="button button--secondary nested-editor-add-button"
              type="button"
              onClick={addLimit}
              disabled={formState.regionalCreditLimits.length >= 100}
            >
              Добавить регион
            </button>
          </div>
          <div className="nested-editor-list">
            {optionsQuery.data.truncated ? (
              <Notice as="p" tone="error" role="alert" className="form-error">
            Для поиска остальных значений используйте поле поиска в справочнике или кнопку «Показать ещё варианты».
          </Notice>
            ) : null}
            {formState.regionalCreditLimits.length === 0 ? (
              <div className="bank-program-empty">
                <strong>Региональные лимиты не заданы</strong>
                <p>Будет использоваться общий федеральный лимит.</p>
              </div>
            ) : null}
            {formState.regionalCreditLimits.map((limit, index) => {
              const rowErrors = errors.limits[limit.key] ?? {}
              return (
                <fieldset className="nested-editor-card" key={limit.key}>
                  <legend>Региональный лимит {index + 1}</legend>
                  <div className="nested-editor-card__heading">
                    <strong>Регион и сумма</strong>
                    <button
                      className="text-button text-button--danger"
                      type="button"
                      onClick={() => removeLimit(limit.key)}
                      aria-label={`Удалить региональный лимит ${index + 1}`}
                    >
                      Удалить
                    </button>
                  </div>
                  <div className="field-grid nested-editor-fields">
                    <RemoteSelect
                      dictionary="regions" label={"Регион"}
                      value={limit.regionId} onChange={(value) => updateLimit(
                          limit.key,
                          'regionId',
                          value,
                        )}
                      initialOptions={(regions ?? []).map((option) => ({ id: option.id, label: option.name }))}
                      truncated={optionsQuery.data.truncated}
                      error={rowErrors.regionId}
                      required
                    />
                    <label className="form-field">
                      Лимит, ₽ *
                      <input
                        name={`regionalCreditLimits.${index}.creditLimit`}
                        type="number"
                        min="0"
                        max="9999999999999.99"
                        step="0.01"
                        inputMode="decimal"
                        value={limit.creditLimit}
                        onChange={(event) => updateLimit(
                          limit.key,
                          'creditLimit',
                          event.target.value,
                        )}
                        required
                        aria-invalid={Boolean(rowErrors.creditLimit)}
                      />
                      {rowErrors.creditLimit ? (
                        <span className="field-error">
                          {rowErrors.creditLimit}
                        </span>
                      ) : null}
                    </label>
                    <label className="developer-active-field nested-editor-status">
                      <input
                        type="checkbox"
                        checked={limit.isActive}
                        onChange={(event) => updateLimit(
                          limit.key,
                          'isActive',
                          event.target.checked,
                        )}
                      />
                      <span><strong>Активен</strong><small>Участвует в расчётах.</small></span>
                    </label>
                  </div>
                </fieldset>
              )
            })}
          </div>
        </section>
        {mutation.isError ? (
          <Notice as="p" tone="error" role="alert" className="form-error">
            {apiErrorMessage(mutation.error)
              ?? 'Не удалось сохранить программу. Повторите попытку.'}
          </Notice>
        ) : null}
        <div className="customer-form-actions">
          {backLink}
          <button
            className="button button--primary"
            type="submit"
            disabled={mutation.isPending}
          >
            {mutation.isPending
              ? 'Сохраняем…'
              : isEditing ? 'Сохранить изменения' : 'Создать программу'}
          </button>
        </div>
      </form>
    </div>
  )
}
