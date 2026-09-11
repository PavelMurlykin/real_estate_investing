import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  createLocationDictionaryEntry,
  deleteLocationDictionaryEntry,
  locationDictionaryDetailQueryOptions,
  locationDictionaryListQueryOptions,
  locationDictionaryOptionsQueryOptions,
  sessionQueryOptions,
  updateLocationDictionaryEntry,
} from '@/api/queries'
import { locationDictionaryKeySchema } from '@/api/schemas'
import type {
  LocationDictionaryEntry,
  LocationDictionaryKey,
  LocationDictionaryWriteRequest,
} from '@/api/schemas'
import { formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type LocationDictionaryConfiguration = {
  key: LocationDictionaryKey
  legacyKey: string
  title: string
  singular: string
  nameLabel: string
  description: string
}

type LocationFormState = {
  name: string
  code: string
  regionId: string
  cityId: string
  metroLineId: string
  isActive: boolean
}

type FieldErrors = Record<string, string>

const locationDictionaryConfigurations: LocationDictionaryConfiguration[] = [
  {
    key: 'regions',
    legacyKey: 'region',
    title: 'Регионы',
    singular: 'регион',
    nameLabel: 'Название региона',
    description: 'Регионы присутствия застройщиков, объектов и программ.',
  },
  {
    key: 'cities',
    legacyKey: 'city',
    title: 'Города',
    singular: 'город',
    nameLabel: 'Название города',
    description: 'Города с обязательной привязкой к региону.',
  },
  {
    key: 'districts',
    legacyKey: 'district',
    title: 'Районы',
    singular: 'район',
    nameLabel: 'Название района',
    description: 'Районы городов, используемые в карточках жилых комплексов.',
  },
  {
    key: 'metro',
    legacyKey: 'metro',
    title: 'Метро',
    singular: 'станцию',
    nameLabel: 'Название станции',
    description: 'Станции и линии метро с фильтрацией по городу.',
  },
]

const emptyFormState: LocationFormState = {
  name: '',
  code: '',
  regionId: '',
  cityId: '',
  metroLineId: '',
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
  if (
    !(error instanceof ApiError)
    || !error.details
    || typeof error.details !== 'object'
    || Array.isArray(error.details)
  ) {
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

type LocationDictionaryEditorProps = {
  configuration: LocationDictionaryConfiguration
  dictionaryKey: LocationDictionaryKey
  entry: LocationDictionaryEntry | null
}

function LocationDictionaryEditor({
  configuration,
  dictionaryKey,
  entry,
}: LocationDictionaryEditorProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const isEditing = entry !== null
  const [formState, setFormState] = useState<LocationFormState>(() => ({
    name: entry?.name ?? '',
    code: entry?.code ?? '',
    regionId: entry?.region ? String(entry.region.id) : '',
    cityId: entry?.city ? String(entry.city.id) : '',
    metroLineId: entry?.metroLine ? String(entry.metroLine.id) : '',
    isActive: entry?.isActive ?? true,
  }))
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const optionsQuery = useQuery(locationDictionaryOptionsQueryOptions(
    formState.regionId,
    formState.cityId,
  ))
  const saveMutation = useMutation({
    mutationFn: (payload: LocationDictionaryWriteRequest) => isEditing
      ? updateLocationDictionaryEntry(dictionaryKey, entry.id, payload)
      : createLocationDictionaryEntry(dictionaryKey, payload),
    onSuccess: async (savedEntry) => {
      await queryClient.invalidateQueries({
        queryKey: ['location-dictionaries', dictionaryKey],
      })
      queryClient.setQueryData(
        ['location-dictionary', dictionaryKey, savedEntry.id],
        savedEntry,
      )
      setFormState(emptyFormState)
      setFieldErrors({})
      navigate(`/locations/${dictionaryKey}`)
    },
    onError: (error) => setFieldErrors(parseApiErrors(error)),
  })

  const updateFormField = <FieldName extends keyof LocationFormState>(
    fieldName: FieldName,
    value: LocationFormState[FieldName],
  ) => {
    setFormState((current) => ({ ...current, [fieldName]: value }))
    setFieldErrors((current) => ({ ...current, [fieldName]: '' }))
  }

  const updateRegion = (regionId: string) => {
    setFormState((current) => ({
      ...current,
      regionId,
      cityId: '',
      metroLineId: '',
    }))
    setFieldErrors((current) => ({
      ...current,
      regionId: '',
      cityId: '',
      metroLineId: '',
    }))
  }

  const updateCity = (cityId: string) => {
    setFormState((current) => ({
      ...current,
      cityId,
      metroLineId: '',
    }))
    setFieldErrors((current) => ({
      ...current,
      cityId: '',
      metroLineId: '',
    }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const errors: FieldErrors = {}
    if (!formState.name.trim()) errors.name = 'Укажите название.'
    if (dictionaryKey === 'regions' && !formState.code.trim()) {
      errors.code = 'Укажите код региона.'
    }
    if (dictionaryKey !== 'regions' && !formState.regionId) {
      errors.regionId = 'Выберите регион.'
    }
    if (
      (dictionaryKey === 'districts' || dictionaryKey === 'metro')
      && !formState.cityId
    ) {
      errors.cityId = 'Выберите город.'
    }
    if (dictionaryKey === 'metro' && !formState.metroLineId) {
      errors.metroLineId = 'Выберите линию метро.'
    }
    setFieldErrors(errors)
    if (Object.keys(errors).length) return

    const payload: LocationDictionaryWriteRequest = {
      name: formState.name.trim(),
      isActive: formState.isActive,
    }
    if (dictionaryKey === 'regions') payload.code = formState.code.trim()
    if (dictionaryKey === 'cities') {
      payload.regionId = Number(formState.regionId)
    }
    if (dictionaryKey === 'districts') {
      payload.cityId = Number(formState.cityId)
    }
    if (dictionaryKey === 'metro') {
      payload.metroLineId = Number(formState.metroLineId)
    }
    saveMutation.mutate(payload)
  }

  const requiresRegion = dictionaryKey !== 'regions'
  const requiresCity = dictionaryKey === 'districts' || dictionaryKey === 'metro'

  return (
    <aside
      className="dictionary-form-card"
      aria-labelledby="location-form-title"
    >
      <span className="eyebrow">Управление локациями</span>
      <h2 id="location-form-title">
        {isEditing
          ? 'Редактирование записи'
          : `Добавить ${configuration.singular}`}
      </h2>
      {optionsQuery.isError ? (
        <p className="form-error" role="alert">
          Не удалось загрузить связанные справочники.
        </p>
      ) : null}
      <form noValidate onSubmit={handleSubmit}>
        <div className="form-field">
          <label htmlFor="location-name">{configuration.nameLabel} *</label>
          <input
            id="location-name"
            value={formState.name}
            maxLength={100}
            aria-invalid={Boolean(fieldErrors.name)}
            aria-describedby={fieldErrors.name
              ? 'location-name-error'
              : undefined}
            onChange={(event) => updateFormField('name', event.target.value)}
          />
          <FieldError id="location-name-error" message={fieldErrors.name} />
        </div>

        {dictionaryKey === 'regions' ? (
          <div className="form-field">
            <label htmlFor="location-code">Код региона *</label>
            <input
              id="location-code"
              value={formState.code}
              maxLength={10}
              aria-invalid={Boolean(fieldErrors.code)}
              aria-describedby={fieldErrors.code
                ? 'location-code-error'
                : undefined}
              onChange={(event) => updateFormField('code', event.target.value)}
            />
            <FieldError id="location-code-error" message={fieldErrors.code} />
          </div>
        ) : null}

        {requiresRegion ? (
          <div className="form-field">
            <label htmlFor="location-region">Регион *</label>
            <select
              id="location-region"
              value={formState.regionId}
              disabled={optionsQuery.isLoading}
              aria-invalid={Boolean(fieldErrors.regionId)}
              aria-describedby={fieldErrors.regionId
                ? 'location-region-error'
                : undefined}
              onChange={(event) => updateRegion(event.target.value)}
            >
              <option value="">Выберите регион</option>
              {optionsQuery.data?.regions.map((region) => (
                <option key={region.id} value={region.id}>{region.name}</option>
              ))}
            </select>
            <FieldError
              id="location-region-error"
              message={fieldErrors.regionId}
            />
          </div>
        ) : null}

        {requiresCity ? (
          <div className="form-field">
            <label htmlFor="location-city">Город *</label>
            <select
              id="location-city"
              value={formState.cityId}
              disabled={!formState.regionId || optionsQuery.isFetching}
              aria-invalid={Boolean(fieldErrors.cityId)}
              aria-describedby={fieldErrors.cityId
                ? 'location-city-error'
                : undefined}
              onChange={(event) => updateCity(event.target.value)}
            >
              <option value="">Выберите город</option>
              {optionsQuery.data?.cities.map((city) => (
                <option key={city.id} value={city.id}>{city.name}</option>
              ))}
            </select>
            <FieldError
              id="location-city-error"
              message={fieldErrors.cityId}
            />
          </div>
        ) : null}

        {dictionaryKey === 'metro' ? (
          <div className="form-field">
            <label htmlFor="location-metro-line">Линия метро *</label>
            <select
              id="location-metro-line"
              value={formState.metroLineId}
              disabled={!formState.cityId || optionsQuery.isFetching}
              aria-invalid={Boolean(fieldErrors.metroLineId)}
              aria-describedby={fieldErrors.metroLineId
                ? 'location-metro-line-error'
                : undefined}
              onChange={(event) => updateFormField(
                'metroLineId',
                event.target.value,
              )}
            >
              <option value="">Выберите линию</option>
              {optionsQuery.data?.metroLines.map((metroLine) => (
                <option key={metroLine.id} value={metroLine.id}>
                  {metroLine.name}
                </option>
              ))}
            </select>
            <FieldError
              id="location-metro-line-error"
              message={fieldErrors.metroLineId}
            />
          </div>
        ) : null}

        {optionsQuery.data && Object.values(optionsQuery.data.truncated).some(
          Boolean,
        ) ? (
          <p className="field-hint">
            Показана ограниченная часть связанных записей.
          </p>
        ) : null}

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
            disabled={saveMutation.isPending || optionsQuery.isError}
          >
            {saveMutation.isPending ? 'Сохраняем…' : 'Сохранить'}
          </button>
          {isEditing ? (
            <>
              <Link
                className="button button--secondary"
                to={`/locations/${dictionaryKey}`}
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

function MetroLineLabel({ entry }: { entry: LocationDictionaryEntry }) {
  if (!entry.metroLine) return <>—</>
  return (
    <span className="location-line-label">
      <span
        className="location-line-swatch"
        style={{ backgroundColor: entry.metroLine.color }}
        aria-hidden="true"
      />
      <span>{entry.metroLine.name}</span>
    </span>
  )
}

export function LocationDictionaryPage() {
  const { dictionaryKey: routeDictionaryKey = '', entryId = '' } = useParams()
  const parsedDictionaryKey = locationDictionaryKeySchema.safeParse(
    routeDictionaryKey,
  )
  const dictionaryKey = parsedDictionaryKey.success
    ? parsedDictionaryKey.data
    : 'regions'
  const configuration = locationDictionaryConfigurations.find(
    (item) => item.key === dictionaryKey,
  ) as LocationDictionaryConfiguration
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
    ...locationDictionaryListQueryOptions(dictionaryKey, searchParameters),
    enabled: parsedDictionaryKey.success,
  })
  const detailQuery = useQuery({
    ...locationDictionaryDetailQueryOptions(
      dictionaryKey,
      dictionaryEntryIdentifier,
    ),
    enabled: parsedDictionaryKey.success && isEditing
      && hasValidEntryIdentifier,
  })
  const filterOptionsQuery = useQuery(locationDictionaryOptionsQueryOptions(
    searchParameters.get('regionId') ?? '',
    searchParameters.get('cityId') ?? '',
  ))
  const [selectedEntry, setSelectedEntry] = (
    useState<LocationDictionaryEntry | null>(null)
  )
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null)
  const deleteCancelButtonRef = useRef<HTMLButtonElement>(null)
  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  useDocumentTitle(`Локации · ${configuration.title}`)

  const deleteMutation = useMutation({
    mutationFn: (entry: LocationDictionaryEntry) => (
      deleteLocationDictionaryEntry(dictionaryKey, entry.id)
    ),
    onSuccess: async (_data, deletedEntry) => {
      setSelectedEntry(null)
      await queryClient.invalidateQueries({
        queryKey: ['location-dictionaries', dictionaryKey],
      })
      queryClient.removeQueries({
        queryKey: ['location-dictionary', dictionaryKey, deletedEntry.id],
      })
      if (dictionaryEntryIdentifier === deletedEntry.id) {
        navigate(`/locations/${dictionaryKey}`)
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

  const updateRegionFilter = (regionId: string) => {
    updateParameters({
      regionId,
      cityId: null,
      metroLineId: null,
      page: null,
    })
  }

  const updateCityFilter = (cityId: string) => {
    updateParameters({ cityId, metroLineId: null, page: null })
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
    entry: LocationDictionaryEntry,
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
        description="Выберите доступный справочник в разделе локаций."
        action={(
          <Link className="button button--secondary" to="/locations/regions">
            К локациям
          </Link>
        )}
      />
    )
  }
  if (
    listQuery.isLoading
    || filterOptionsQuery.isLoading
    || (isEditing && sessionQuery.isLoading)
  ) {
    return <PageLoadingState />
  }
  if (listQuery.isError || !listQuery.data) {
    return <ErrorState onRetry={() => void listQuery.refetch()} />
  }
  if (filterOptionsQuery.isError || !filterOptionsQuery.data) {
    return <ErrorState onRetry={() => void filterOptionsQuery.refetch()} />
  }
  if (isEditing && !canManageCatalogs) {
    return (
      <EmptyState
        title="Недостаточно прав"
        description="Редактировать общие локации могут только модераторы."
        action={(
          <Link
            className="button button--secondary"
            to={`/locations/${dictionaryKey}`}
          >
            К списку
          </Link>
        )}
      />
    )
  }
  if (isEditing && detailQuery.isLoading) return <PageLoadingState />
  if (isEditing && (detailQuery.isError || !detailQuery.data)) {
    return <ErrorState onRetry={() => void detailQuery.refetch()} />
  }

  const { results, page, totalCount, totalPages } = listQuery.data
  const options = filterOptionsQuery.data
  const showRegion = dictionaryKey !== 'regions'
  const showCity = dictionaryKey === 'districts' || dictionaryKey === 'metro'
  const showMetroLine = dictionaryKey === 'metro'
  const legacyCatalogUrl = `/locations/?model=${configuration.legacyKey}`

  return (
    <div className="page-stack location-dictionary-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Справочники</span>
          <h1>Локации</h1>
          <p>{configuration.description}</p>
        </div>
        <div className="page-header__actions">
          <a className="button button--secondary" href={legacyCatalogUrl}>
            Прежняя версия
          </a>
        </div>
      </header>

      <nav className="dictionary-tabs" aria-label="Справочники локаций">
        {locationDictionaryConfigurations.map((item) => (
          <Link
            key={item.key}
            to={`/locations/${item.key}`}
            aria-current={item.key === dictionaryKey ? 'page' : undefined}
          >
            {item.title}
          </Link>
        ))}
      </nav>

      <section
        className="filter-panel location-filter-panel"
        aria-label={`Фильтры: ${configuration.title}`}
      >
        <form className="search-form" role="search" onSubmit={handleSearch}>
          <label htmlFor="location-search">Поиск</label>
          <div className="search-control">
            <span aria-hidden="true">⌕</span>
            <input
              id="location-search"
              name="q"
              type="search"
              key={searchParameters.get('q') ?? ''}
              defaultValue={searchParameters.get('q') ?? ''}
              placeholder="Название или связанная локация"
            />
            <button className="button button--dark" type="submit">Найти</button>
          </div>
        </form>
        {showRegion ? (
          <div className="sort-control">
            <label htmlFor="location-filter-region">Регион</label>
            <select
              id="location-filter-region"
              value={searchParameters.get('regionId') ?? ''}
              onChange={(event) => updateRegionFilter(event.target.value)}
            >
              <option value="">Все регионы</option>
              {options.regions.map((region) => (
                <option key={region.id} value={region.id}>{region.name}</option>
              ))}
            </select>
          </div>
        ) : null}
        {showCity ? (
          <div className="sort-control">
            <label htmlFor="location-filter-city">Город</label>
            <select
              id="location-filter-city"
              value={searchParameters.get('cityId') ?? ''}
              disabled={!searchParameters.get('regionId')}
              onChange={(event) => updateCityFilter(event.target.value)}
            >
              <option value="">Все города</option>
              {options.cities.map((city) => (
                <option key={city.id} value={city.id}>{city.name}</option>
              ))}
            </select>
          </div>
        ) : null}
        {showMetroLine ? (
          <div className="sort-control">
            <label htmlFor="location-filter-line">Линия метро</label>
            <select
              id="location-filter-line"
              value={searchParameters.get('metroLineId') ?? ''}
              disabled={!searchParameters.get('cityId')}
              onChange={(event) => updateParameters({
                metroLineId: event.target.value,
                page: null,
              })}
            >
              <option value="">Все линии</option>
              {options.metroLines.map((metroLine) => (
                <option key={metroLine.id} value={metroLine.id}>
                  {metroLine.name}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        <div className="sort-control">
          <label htmlFor="location-status">Статус</label>
          <select
            id="location-status"
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
          <label htmlFor="location-ordering">Сортировка</label>
          <select
            id="location-ordering"
            value={searchParameters.get('ordering') ?? 'default'}
            onChange={(event) => updateParameters({
              ordering: event.target.value,
              page: null,
            })}
          >
            {orderingOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </section>

      <div className="results-heading" aria-live="polite">
        <p>{configuration.title}: <strong>{formatInteger(totalCount)}</strong></p>
        {listQuery.isFetching || filterOptionsQuery.isFetching
          ? <span>Обновляем…</span>
          : null}
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
                <table className="property-table catalog-table location-table">
                  <caption className="visually-hidden">
                    {configuration.title}
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">{configuration.nameLabel}</th>
                      {dictionaryKey === 'regions'
                        ? <th scope="col">Код</th>
                        : null}
                      {showRegion ? <th scope="col">Регион</th> : null}
                      {showCity ? <th scope="col">Город</th> : null}
                      {showMetroLine ? <th scope="col">Линия</th> : null}
                      <th scope="col">Используется</th>
                      <th scope="col">Статус</th>
                      {canManageCatalogs ? (
                        <th scope="col">
                          <span className="visually-hidden">Действия</span>
                        </th>
                      ) : null}
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((entry) => (
                      <tr key={entry.id}>
                        <td><strong>{entry.name}</strong></td>
                        {dictionaryKey === 'regions'
                          ? <td>{entry.code ?? '—'}</td>
                          : null}
                        {showRegion
                          ? <td>{entry.region?.name ?? '—'}</td>
                          : null}
                        {showCity
                          ? <td>{entry.city?.name ?? '—'}</td>
                          : null}
                        {showMetroLine
                          ? <td><MetroLineLabel entry={entry} /></td>
                          : null}
                        <td>{formatInteger(entry.usageCount)}</td>
                        <td>{entry.isActive ? 'Активна' : 'Неактивна'}</td>
                        {canManageCatalogs ? (
                          <td>
                            <div className="row-actions">
                              <Link
                                className="row-action"
                                to={`/locations/${dictionaryKey}/${entry.id}/edit`}
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
                  <article
                    className="property-mobile-card catalog-mobile-card"
                    key={entry.id}
                  >
                    <div className="property-mobile-card__heading">
                      <div>
                        <span>{configuration.title}</span>
                        <h2>{entry.name}</h2>
                      </div>
                      <span className={entry.isActive
                        ? 'catalog-status'
                        : 'catalog-status catalog-status--inactive'}
                      >
                        {entry.isActive ? 'Активна' : 'Неактивна'}
                      </span>
                    </div>
                    <dl>
                      {entry.code ? (
                        <div><dt>Код</dt><dd>{entry.code}</dd></div>
                      ) : null}
                      {entry.region ? (
                        <div><dt>Регион</dt><dd>{entry.region.name}</dd></div>
                      ) : null}
                      {entry.city ? (
                        <div><dt>Город</dt><dd>{entry.city.name}</dd></div>
                      ) : null}
                      {entry.metroLine ? (
                        <div>
                          <dt>Линия</dt>
                          <dd><MetroLineLabel entry={entry} /></dd>
                        </div>
                      ) : null}
                      <div>
                        <dt>Используется</dt>
                        <dd>{formatInteger(entry.usageCount)}</dd>
                      </div>
                    </dl>
                    {canManageCatalogs ? (
                      <Link
                        className="text-link"
                        to={`/locations/${dictionaryKey}/${entry.id}/edit`}
                      >
                        Редактировать
                      </Link>
                    ) : null}
                  </article>
                ))}
              </div>
            </>
          )}

          {totalPages > 1 ? (
            <nav
              className="pagination"
              aria-label={`Страницы: ${configuration.title}`}
            >
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => updateParameters({
                  page: String(page - 1),
                })}
              >
                <span aria-hidden="true">←</span> Назад
              </button>
              <span>Страница <strong>{page}</strong> из {totalPages}</span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => updateParameters({
                  page: String(page + 1),
                })}
              >
                Далее <span aria-hidden="true">→</span>
              </button>
            </nav>
          ) : null}
        </section>

        {canManageCatalogs ? (
          <LocationDictionaryEditor
            key={`${dictionaryKey}:${detailQuery.data?.id ?? 'new'}`}
            configuration={configuration}
            dictionaryKey={dictionaryKey}
            entry={detailQuery.data ?? null}
          />
        ) : null}
      </div>

      {selectedEntry ? (
        <div
          className="confirmation-dialog-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) closeDeleteDialog()
          }}
        >
          <section
            className="confirmation-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="location-delete-title"
            aria-describedby="location-delete-description"
          >
            <span className="eyebrow">Подтверждение</span>
            <h2 id="location-delete-title">Удалить локацию?</h2>
            <p id="location-delete-description">
              «{selectedEntry.name}» будет удалена. Связанных записей:{' '}
              {formatInteger(selectedEntry.usageCount)}.
            </p>
            {deleteMutation.isError ? (
              <p className="form-error" role="alert">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'Локация используется в других разделах и не может быть удалена.'
                  : 'Не удалось удалить локацию. Повторите попытку.'}
              </p>
            ) : null}
            <div className="confirmation-dialog__actions">
              <button
                className="button button--secondary"
                type="button"
                ref={deleteCancelButtonRef}
                disabled={deleteMutation.isPending}
                onClick={closeDeleteDialog}
              >
                Отмена
              </button>
              <button
                className="button button--danger"
                type="button"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(selectedEntry)}
              >
                {deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}
