import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  createPropertyDictionaryEntry,
  deletePropertyDictionaryEntry,
  propertyDictionaryDetailQueryOptions,
  propertyDictionaryListQueryOptions,
  sessionQueryOptions,
  updatePropertyDictionaryEntry,
} from '@/api/queries'
import {
  propertyDictionaryKeySchema,
} from '@/api/schemas'
import type {
  PropertyDictionaryEntry,
  PropertyDictionaryKey,
  PropertyDictionaryWriteRequest,
} from '@/api/schemas'
import { formatDateTime, formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type DictionaryConfiguration = {
  key: PropertyDictionaryKey
  legacyKey: string
  title: string
  singular: string
  description: string
  hasWeight: boolean
}

type DictionaryFormState = {
  name: string
  description: string
  weight: string
  isActive: boolean
}

type FieldErrors = Record<string, string>

const dictionaryConfigurations: DictionaryConfiguration[] = [
  {
    key: 'real-estate-types',
    legacyKey: 'real_estate_type',
    title: 'Типы недвижимости',
    singular: 'тип недвижимости',
    description: 'Категории объектов, используемые в жилых комплексах.',
    hasWeight: false,
  },
  {
    key: 'real-estate-classes',
    legacyKey: 'real_estate_class',
    title: 'Классы ЖК',
    singular: 'класс ЖК',
    description: 'Классы проектов и их коэффициенты для расчётов.',
    hasWeight: true,
  },
  {
    key: 'apartment-layouts',
    legacyKey: 'apartment_layout',
    title: 'Планировки',
    singular: 'планировку',
    description: 'Варианты планировок объектов недвижимости.',
    hasWeight: false,
  },
  {
    key: 'apartment-decorations',
    legacyKey: 'apartment_decoration',
    title: 'Отделки',
    singular: 'тип отделки',
    description: 'Варианты отделки объектов недвижимости.',
    hasWeight: false,
  },
  {
    key: 'window-views',
    legacyKey: 'window_view',
    title: 'Виды из окна',
    singular: 'вид из окна',
    description: 'Характеристики вида из окон объекта.',
    hasWeight: false,
  },
  {
    key: 'transport-accessibility-types',
    legacyKey: 'transport_accessibility_type',
    title: 'Способы до метро',
    singular: 'способ доступности',
    description: 'Способы добраться от жилого комплекса до метро.',
    hasWeight: false,
  },
]

const emptyFormState: DictionaryFormState = {
  name: '',
  description: '',
  weight: '',
  isActive: true,
}

const orderingOptions = [
  { value: 'default', label: 'По умолчанию' },
  { value: 'name', label: 'По названию: А–Я' },
  { value: '-name', label: 'По названию: Я–А' },
  { value: '-updatedAt', label: 'Сначала изменённые' },
]

function findFirstError(value: unknown): string | undefined {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = findFirstError(item)
      if (message) return message
    }
  }
  if (value && typeof value === 'object') {
    for (const item of Object.values(value)) {
      const message = findFirstError(item)
      if (message) return message
    }
  }
  return undefined
}

function parseApiErrors(error: unknown): FieldErrors {
  if (!(error instanceof ApiError) || !error.details
    || typeof error.details !== 'object' || Array.isArray(error.details)) {
    return { form: 'Не удалось сохранить запись. Повторите попытку.' }
  }
  const errors: FieldErrors = {}
  Object.entries(error.details).forEach(([fieldName, value]) => {
    const message = findFirstError(value)
    if (message) errors[fieldName] = message
  })
  return Object.keys(errors).length
    ? errors
    : { form: 'Не удалось сохранить запись. Повторите попытку.' }
}

function FieldError({ id, message }: { id: string, message?: string }) {
  return message
    ? <span className="field-error" id={id}>{message}</span>
    : null
}

type PropertyDictionaryEditorProps = {
  configuration: DictionaryConfiguration
  dictionaryKey: PropertyDictionaryKey
  entry: PropertyDictionaryEntry | null
}

function PropertyDictionaryEditor({
  configuration,
  dictionaryKey,
  entry,
}: PropertyDictionaryEditorProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const isEditing = entry !== null
  const [formState, setFormState] = useState<DictionaryFormState>(() => ({
    name: entry?.name ?? '',
    description: entry?.description ?? '',
    weight: entry?.weight ?? '',
    isActive: entry?.isActive ?? true,
  }))
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const saveMutation = useMutation({
    mutationFn: (payload: PropertyDictionaryWriteRequest) => isEditing
      ? updatePropertyDictionaryEntry(dictionaryKey, entry.id, payload)
      : createPropertyDictionaryEntry(dictionaryKey, payload),
    onSuccess: async (savedEntry) => {
      await queryClient.invalidateQueries({
        queryKey: ['property-dictionaries', dictionaryKey],
      })
      queryClient.setQueryData(
        ['property-dictionary', dictionaryKey, savedEntry.id],
        savedEntry,
      )
      setFormState(emptyFormState)
      setFieldErrors({})
      navigate(`/dictionaries/${dictionaryKey}`)
    },
    onError: (error) => setFieldErrors(parseApiErrors(error)),
  })

  const updateFormField = <FieldName extends keyof DictionaryFormState>(
    fieldName: FieldName,
    value: DictionaryFormState[FieldName],
  ) => {
    setFormState((current) => ({ ...current, [fieldName]: value }))
    setFieldErrors((current) => ({ ...current, [fieldName]: '' }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const errors: FieldErrors = {}
    if (!formState.name.trim()) errors.name = 'Укажите название.'
    const normalizedWeight = formState.weight.trim().replace(',', '.')
    if (configuration.hasWeight && !/^-?\d{1,3}(\.\d{1,2})?$/.test(
      normalizedWeight,
    )) {
      errors.weight = 'Укажите коэффициент с точностью до двух знаков.'
    }
    setFieldErrors(errors)
    if (Object.keys(errors).length) return

    saveMutation.mutate({
      name: formState.name.trim(),
      description: formState.description.trim() || null,
      ...(configuration.hasWeight ? { weight: normalizedWeight } : {}),
      isActive: formState.isActive,
    })
  }

  return (
    <aside className="dictionary-form-card" aria-labelledby="dictionary-form-title">
      <span className="eyebrow">Управление справочником</span>
      <h2 id="dictionary-form-title">
        {isEditing
          ? 'Редактирование записи'
          : `Добавить ${configuration.singular}`}
      </h2>
      <form noValidate onSubmit={handleSubmit}>
        <div className="form-field">
          <label htmlFor="dictionary-name">Название *</label>
          <input
            id="dictionary-name"
            value={formState.name}
            maxLength={100}
            aria-invalid={Boolean(fieldErrors.name)}
            aria-describedby={fieldErrors.name
              ? 'dictionary-name-error'
              : undefined}
            onChange={(event) => updateFormField('name', event.target.value)}
          />
          <FieldError id="dictionary-name-error" message={fieldErrors.name} />
        </div>
        {configuration.hasWeight ? (
          <div className="form-field">
            <label htmlFor="dictionary-weight">Коэффициент *</label>
            <input
              id="dictionary-weight"
              inputMode="decimal"
              value={formState.weight}
              placeholder="1.20"
              aria-invalid={Boolean(fieldErrors.weight)}
              aria-describedby={fieldErrors.weight
                ? 'dictionary-weight-error'
                : undefined}
              onChange={(event) => updateFormField(
                'weight',
                event.target.value,
              )}
            />
            <FieldError
              id="dictionary-weight-error"
              message={fieldErrors.weight}
            />
          </div>
        ) : null}
        <div className="form-field">
          <label htmlFor="dictionary-description">Описание</label>
          <textarea
            id="dictionary-description"
            rows={5}
            value={formState.description}
            onChange={(event) => updateFormField(
              'description',
              event.target.value,
            )}
          />
        </div>
        <label className="developer-active-field">
          <input
            type="checkbox"
            checked={formState.isActive}
            onChange={(event) => updateFormField(
              'isActive',
              event.target.checked,
            )}
          />
          <span>Запись активна</span>
        </label>
        {fieldErrors.form ? (
          <p className="form-error" role="alert">{fieldErrors.form}</p>
        ) : null}
        <div className="dictionary-form-actions">
          <button
            className="button button--primary"
            type="submit"
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending ? 'Сохраняем…' : 'Сохранить'}
          </button>
          {isEditing ? (
            <>
              <Link
                className="button button--secondary"
                to={`/dictionaries/${dictionaryKey}`}
              >
                Отмена
              </Link>
              <a className="text-link" href={entry.legacyEditUrl}>
                Django-форма
              </a>
            </>
          ) : null}
        </div>
      </form>
    </aside>
  )
}

export function PropertyDictionaryPage() {
  const { dictionaryKey: routeDictionaryKey = '', entryId = '' } = useParams()
  const parsedDictionaryKey = propertyDictionaryKeySchema.safeParse(
    routeDictionaryKey,
  )
  const dictionaryKey = parsedDictionaryKey.success
    ? parsedDictionaryKey.data
    : 'real-estate-types'
  const configuration = dictionaryConfigurations.find(
    (item) => item.key === dictionaryKey,
  ) as DictionaryConfiguration
  const dictionaryEntryIdentifier = Number(entryId)
  const isEditing = entryId !== ''
  const hasValidEntryIdentifier = !isEditing || (
    Number.isInteger(dictionaryEntryIdentifier) && dictionaryEntryIdentifier > 0
  )
  const [searchParameters, setSearchParameters] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const sessionQuery = useQuery(sessionQueryOptions)
  const listQuery = useQuery({
    ...propertyDictionaryListQueryOptions(dictionaryKey, searchParameters),
    enabled: parsedDictionaryKey.success,
  })
  const detailQuery = useQuery({
    ...propertyDictionaryDetailQueryOptions(
      dictionaryKey,
      dictionaryEntryIdentifier,
    ),
    enabled: parsedDictionaryKey.success && isEditing
      && hasValidEntryIdentifier,
  })
  const [selectedEntry, setSelectedEntry] = (
    useState<PropertyDictionaryEntry | null>(null)
  )
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null)
  const deleteCancelButtonRef = useRef<HTMLButtonElement>(null)
  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  useDocumentTitle(`Справочники · ${configuration.title}`)

  const deleteMutation = useMutation({
    mutationFn: (entry: PropertyDictionaryEntry) => (
      deletePropertyDictionaryEntry(dictionaryKey, entry.id)
    ),
    onSuccess: async (_data, deletedEntry) => {
      setSelectedEntry(null)
      await queryClient.invalidateQueries({
        queryKey: ['property-dictionaries', dictionaryKey],
      })
      queryClient.removeQueries({
        queryKey: ['property-dictionary', dictionaryKey, deletedEntry.id],
      })
      if (dictionaryEntryIdentifier === deletedEntry.id) {
        navigate(`/dictionaries/${dictionaryKey}`)
      }
      window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
    },
  })

  useEffect(() => {
    if (!selectedEntry) return
    deleteCancelButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleteMutation.isPending) {
        setSelectedEntry(null)
        window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [deleteMutation.isPending, selectedEntry])

  const updateParameters = (updates: Record<string, string | null>) => {
    const nextParameters = new URLSearchParams(searchParameters)
    Object.entries(updates).forEach(([fieldName, value]) => {
      if (!value || value === 'all' || value === 'default') {
        nextParameters.delete(fieldName)
      } else {
        nextParameters.set(fieldName, value)
      }
    })
    setSearchParameters(nextParameters)
  }

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const searchInput = event.currentTarget.elements.namedItem('q')
    const searchValue = searchInput instanceof HTMLInputElement
      ? searchInput.value.trim()
      : ''
    updateParameters({ q: searchValue || null, page: null })
  }

  const openDeleteDialog = (
    entry: PropertyDictionaryEntry,
    trigger: HTMLButtonElement,
  ) => {
    deleteMutation.reset()
    deleteTriggerRef.current = trigger
    setSelectedEntry(entry)
  }

  const closeDeleteDialog = () => {
    if (deleteMutation.isPending) return
    setSelectedEntry(null)
    window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
  }

  if (!parsedDictionaryKey.success || !hasValidEntryIdentifier) {
    return (
      <EmptyState
        title="Справочник не найден"
        description="Выберите доступный справочник в разделе недвижимости."
        action={(
          <Link className="button button--secondary" to="/dictionaries/real-estate-types">
            К справочникам
          </Link>
        )}
      />
    )
  }
  if (listQuery.isLoading || (isEditing && sessionQuery.isLoading)) {
    return <PageLoadingState />
  }
  if (listQuery.isError || !listQuery.data) {
    return <ErrorState onRetry={() => void listQuery.refetch()} />
  }
  if (isEditing && !canManageCatalogs) {
    return (
      <EmptyState
        title="Недостаточно прав"
        description="Редактировать общие справочники могут только модераторы."
        action={<Link className="button button--secondary" to={`/dictionaries/${dictionaryKey}`}>К списку</Link>}
      />
    )
  }
  if (isEditing && detailQuery.isLoading) return <PageLoadingState />
  if (isEditing && (detailQuery.isError || !detailQuery.data)) {
    return <ErrorState onRetry={() => void detailQuery.refetch()} />
  }

  const { results, page, totalCount, totalPages } = listQuery.data
  const legacyCatalogUrl = (
    `/property/dictionaries/?model=${configuration.legacyKey}`
  )

  return (
    <div className="page-stack property-dictionary-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Недвижимость</span>
          <h1>Справочники объектов</h1>
          <p>{configuration.description}</p>
        </div>
        <div className="page-header__actions">
          <a className="button button--secondary" href={legacyCatalogUrl}>
            Прежняя версия
          </a>
        </div>
      </header>

      <nav className="dictionary-tabs" aria-label="Справочники объектов">
        {dictionaryConfigurations.map((item) => (
          <Link
            key={item.key}
            to={`/dictionaries/${item.key}`}
            aria-current={item.key === dictionaryKey ? 'page' : undefined}
          >
            {item.title}
          </Link>
        ))}
      </nav>

      <section className="filter-panel dictionary-filter-panel" aria-label={`Фильтры: ${configuration.title}`}>
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <label htmlFor="dictionary-search">Поиск</label>
          <div className="search-control">
            <span aria-hidden="true">⌕</span>
            <input
              id="dictionary-search"
              name="q"
              type="search"
              key={searchParameters.get('q') ?? ''}
              defaultValue={searchParameters.get('q') ?? ''}
              placeholder="Название или описание"
            />
            <button className="button button--dark" type="submit">Найти</button>
          </div>
        </form>
        <div className="sort-control">
          <label htmlFor="dictionary-status">Статус</label>
          <select
            id="dictionary-status"
            value={searchParameters.get('status') ?? 'all'}
            onChange={(event) => updateParameters({
              status: event.target.value,
              page: null,
            })}
          >
            <option value="all">Все</option>
            <option value="active">Активные</option>
            <option value="inactive">Неактивные</option>
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="dictionary-ordering">Сортировка</label>
          <select
            id="dictionary-ordering"
            value={searchParameters.get('ordering') ?? 'default'}
            onChange={(event) => updateParameters({
              ordering: event.target.value,
              page: null,
            })}
          >
            {orderingOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
            {configuration.hasWeight ? (
              <option value="-weight">Сначала больший коэффициент</option>
            ) : null}
          </select>
        </div>
      </section>

      <div className="results-heading" aria-live="polite">
        <p>{configuration.title}: <strong>{formatInteger(totalCount)}</strong></p>
        {listQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>

      <div className={canManageCatalogs
        ? 'dictionary-workspace'
        : 'dictionary-workspace dictionary-workspace--public'}
      >
        <section aria-label={configuration.title}>
          {results.length === 0 ? (
            <EmptyState
              title="Записей не найдено"
              description="Измените фильтры или добавьте первую запись."
            />
          ) : (
            <>
              <div className="table-card property-table-wrapper">
                <table className="property-table catalog-table dictionary-table">
                  <caption className="visually-hidden">{configuration.title}</caption>
                  <thead>
                    <tr>
                      <th scope="col">Название</th>
                      <th scope="col">Описание</th>
                      {configuration.hasWeight ? <th scope="col">Коэффициент</th> : null}
                      <th scope="col">Используется</th>
                      <th scope="col">Статус</th>
                      {canManageCatalogs ? <th scope="col"><span className="visually-hidden">Действия</span></th> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((entry) => (
                      <tr key={entry.id}>
                        <td><strong>{entry.name}</strong></td>
                        <td className="dictionary-description">{entry.description || '—'}</td>
                        {configuration.hasWeight ? <td>{entry.weight ?? '—'}</td> : null}
                        <td>{formatInteger(entry.usageCount)}</td>
                        <td>{entry.isActive ? 'Активна' : 'Неактивна'}</td>
                        {canManageCatalogs ? (
                          <td>
                            <div className="row-actions">
                              <Link
                                className="row-action"
                                to={`/dictionaries/${dictionaryKey}/${entry.id}/edit`}
                                aria-label={`Редактировать: ${entry.name}`}
                              >
                                ✎
                              </Link>
                              <button
                                className="row-action row-action--danger"
                                type="button"
                                aria-label={`Удалить: ${entry.name}`}
                                onClick={(event) => openDeleteDialog(
                                  entry,
                                  event.currentTarget,
                                )}
                              >
                                ×
                              </button>
                            </div>
                          </td>
                        ) : null}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="property-mobile-list">
                {results.map((entry) => (
                  <article className="property-mobile-card catalog-mobile-card" key={entry.id}>
                    <div className="property-mobile-card__heading">
                      <div><span>{configuration.title}</span><h2>{entry.name}</h2></div>
                      <span className={entry.isActive ? 'catalog-status' : 'catalog-status catalog-status--inactive'}>
                        {entry.isActive ? 'Активна' : 'Неактивна'}
                      </span>
                    </div>
                    <p>{entry.description || 'Описание не заполнено.'}</p>
                    <dl>
                      {configuration.hasWeight ? <div><dt>Коэффициент</dt><dd>{entry.weight}</dd></div> : null}
                      <div><dt>Используется</dt><dd>{entry.usageCount}</dd></div>
                      <div><dt>Изменено</dt><dd>{formatDateTime(entry.updatedAt)}</dd></div>
                    </dl>
                    {canManageCatalogs ? (
                      <Link className="text-link" to={`/dictionaries/${dictionaryKey}/${entry.id}/edit`}>
                        Редактировать
                      </Link>
                    ) : null}
                  </article>
                ))}
              </div>
            </>
          )}

          {totalPages > 1 ? (
            <nav className="pagination" aria-label={`Страницы: ${configuration.title}`}>
              <button type="button" disabled={page <= 1} onClick={() => updateParameters({ page: String(page - 1) })}>
                <span aria-hidden="true">←</span> Назад
              </button>
              <span>Страница <strong>{page}</strong> из {totalPages}</span>
              <button type="button" disabled={page >= totalPages} onClick={() => updateParameters({ page: String(page + 1) })}>
                Далее <span aria-hidden="true">→</span>
              </button>
            </nav>
          ) : null}
        </section>

        {canManageCatalogs ? (
          <PropertyDictionaryEditor
            key={`${dictionaryKey}:${detailQuery.data?.id ?? 'new'}`}
            configuration={configuration}
            dictionaryKey={dictionaryKey}
            entry={detailQuery.data ?? null}
          />
        ) : null}
      </div>

      {selectedEntry ? (
        <div className="confirmation-dialog-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.currentTarget === event.target) closeDeleteDialog()
        }}>
          <section className="confirmation-dialog" role="alertdialog" aria-modal="true" aria-labelledby="dictionary-delete-title" aria-describedby="dictionary-delete-description">
            <span className="eyebrow">Подтверждение</span>
            <h2 id="dictionary-delete-title">Удалить запись?</h2>
            <p id="dictionary-delete-description">
              «{selectedEntry.name}» будет удалена. Связанных записей: {selectedEntry.usageCount}.
            </p>
            {deleteMutation.isError ? (
              <p className="form-error" role="alert">
                {deleteMutation.error instanceof ApiError && deleteMutation.error.status === 409
                  ? 'Запись используется в других разделах и не может быть удалена.'
                  : 'Не удалось удалить запись. Повторите попытку.'}
              </p>
            ) : null}
            <div className="confirmation-dialog__actions">
              <button className="button button--secondary" type="button" ref={deleteCancelButtonRef} disabled={deleteMutation.isPending} onClick={closeDeleteDialog}>Отмена</button>
              <button className="button button--danger" type="button" disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(selectedEntry)}>
                {deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}
