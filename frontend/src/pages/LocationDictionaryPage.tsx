import { SectionNavigation } from '@/shared/ui/SectionNavigation'
import { retryFailedQueries } from '@/shared/lib/retryFailedQueries'
import { Notice } from '@/shared/ui/Notice'
import { restoreFocus } from '@/shared/lib/restoreFocus'
import { ModalDialog } from '@/shared/ui/ModalDialog'
import { SelectFilter } from '@/shared/ui/SelectFilter'
import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { Pagination } from '@/shared/ui/Pagination'
import { ResetFilters } from '@/shared/ui/ResetFilters'
import { useTableParameters } from '@/shared/lib/useTableParameters'
import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { SortableHeader } from '@/shared/ui/SortableHeader'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'
import { RemoteMultiSelect } from '@/shared/ui/RemoteMultiSelect'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { NationalLocationImportPanel } from './NationalLocationImportPanel'
import type { FormEvent } from 'react'
import { useRef, useState } from 'react'
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
import { LocationImportPanel } from './LocationImportPanel'

type LocationDictionaryConfiguration = {
  key: LocationDictionaryKey
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
  systemId: string
  locationId: string
  lineIds: string[]
  lineColor: string
  locationIsInferred: boolean
  isActive: boolean
}

type FieldErrors = Record<string, string>

const locationDictionaryConfigurations: LocationDictionaryConfiguration[] = [
  {
    key: 'regions',
    title: 'Регионы',
    singular: 'регион',
    nameLabel: 'Название региона',
    description: 'Регионы присутствия застройщиков, объектов и программ.',
  },
  {
    key: 'cities',
    title: 'Города',
    singular: 'город',
    nameLabel: 'Название города',
    description: 'Города с обязательной привязкой к региону.',
  },
  {
    key: 'districts',
    title: 'Административные районы',
    singular: 'район',
    nameLabel: 'Название района',
    description: 'Административные районы, используемые в карточках жилых комплексов.',
  },
  {
    key: 'metro',
    title: 'Метро',
    singular: 'станцию',
    nameLabel: 'Название станции',
    description: 'Станции метро: система, линии и населённый пункт станции.',
  },
  { key: 'metro-lines', title: 'Линии метро', singular: 'линию', nameLabel: 'Название линии', description: 'Линии относятся к системе метро. Прежние связи с городами сохранены.' },
  { key: 'metro-systems', title: 'Системы метро', singular: 'систему', nameLabel: 'Название системы', description: 'Центр системы связан с населённым пунктом. Станции могут находиться в других населённых пунктах и регионах.' },
]

const emptyFormState: LocationFormState = {
  name: '',
  code: '',
  regionId: '',
  cityId: '',
  metroLineId: '',
  systemId: '', locationId: '', lineIds: [], lineColor: '#777777', locationIsInferred: true,
  isActive: true,
}

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
    systemId: entry?.system ? String(entry.system.id) : '',
    locationId: entry?.location ? String(entry.location.id) : '',
    lineIds: entry?.lines?.map((line) => String(line.id)) ?? [],
    lineColor: entry?.lineColor ?? '#777777',
    locationIsInferred: entry?.locationIsInferred ?? true,
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
    if ((dictionaryKey === 'cities' || dictionaryKey === 'districts') && !formState.regionId) {
      errors.regionId = 'Выберите регион.'
    }
    if (
      dictionaryKey === 'districts'
      && !formState.cityId
    ) {
      errors.cityId = 'Выберите город.'
    }
    if (dictionaryKey === 'metro' && !formState.metroLineId) {
      errors.metroLineId = 'Выберите линию метро.'
    }
    if (dictionaryKey === 'metro-lines' && !formState.systemId) errors.systemId = 'Выберите систему метро.'
    if (dictionaryKey === 'metro-systems' && !formState.locationId) errors.locationId = 'Выберите центр системы.'
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
      payload.lineIds = formState.lineIds.map(Number)
      payload.locationId = formState.locationId ? Number(formState.locationId) : null
      payload.locationIsInferred = formState.locationIsInferred
    }
    if (dictionaryKey === 'metro-lines') {
      payload.systemId = Number(formState.systemId)
      payload.lineColor = formState.lineColor
    }
    if (dictionaryKey === 'metro-systems') payload.locationId = Number(formState.locationId)
    saveMutation.mutate(payload)
  }

  const requiresRegion = dictionaryKey === 'cities' || dictionaryKey === 'districts'
  const isMetro = dictionaryKey === 'metro'
  const requiresCity = dictionaryKey === 'districts'

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
        <Notice as="p" tone="error" role="alert" className="form-error">
          Не удалось загрузить связанные справочники.
        </Notice>
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
          <RemoteSelect
            searchable
            dictionary="regions" label={"Регион"}
            value={formState.regionId} onChange={(value) => updateRegion(value)}
            initialOptions={(optionsQuery.data?.regions ?? []).map((option) => ({ id: option.id, label: option.name }))}
            truncated={optionsQuery.data?.truncated.regions}
            disabled={optionsQuery.isLoading}
            error={fieldErrors.regionId}
            required
          />
        ) : null}

        {requiresCity ? (
          <RemoteSelect
            searchable
            dictionary="cities" label={"Город"}
            value={formState.cityId} onChange={(value) => updateCity(value)}
            initialOptions={(optionsQuery.data?.cities ?? []).map((option) => ({ id: option.id, label: option.name }))}
            truncated={optionsQuery.data?.truncated.cities}
            filters={{ regionId: formState.regionId }}
            disabled={!formState.regionId || optionsQuery.isFetching}
            error={fieldErrors.cityId}
            required
          />
        ) : null}

        {dictionaryKey === 'metro-lines' || isMetro ? (
          <RemoteSelect searchable dictionary="metro-systems" label="Система метро"
            value={formState.systemId} truncated
            initialOptions={entry?.system ? [{ id: entry.system.id, label: entry.system.name }] : []}
            onChange={(value) => setFormState((current) => ({ ...current, systemId: value, metroLineId: '', lineIds: [] }))}
            error={fieldErrors.systemId} required />
        ) : null}
        {dictionaryKey === 'metro-systems' || isMetro ? (
          <RemoteSelect searchable dictionary="locations" label={isMetro ? 'Населённый пункт станции' : 'Центр системы'}
            value={formState.locationId} truncated filters={{ category: 'locality' }}
            initialOptions={entry?.location ? [{ id: entry.location.id, label: entry.location.name }] : []}
            onChange={(value) => setFormState((current) => ({ ...current, locationId: value, locationIsInferred: !value }))}
            error={fieldErrors.locationId} required={!isMetro} />
        ) : null}
        {dictionaryKey === 'metro-lines' ? (
          <label className="form-field">Цвет линии *
            <input type="color" value={formState.lineColor} onChange={(event) => updateFormField('lineColor', event.target.value)} />
            <FieldError id="line-color-error" message={fieldErrors.lineColor} />
          </label>
        ) : null}
        {isMetro ? (
          <RemoteSelect searchable
            dictionary="metro-lines" label={"Линия метро"}
            value={formState.metroLineId} onChange={(value) => updateFormField(
                'metroLineId',
                value,
              )}
            initialOptions={entry?.metroLine ? [{ id: entry.metroLine.id, label: entry.metroLine.name }] : []}
            truncated
            filters={{ systemId: formState.systemId }}
            disabled={!formState.systemId && !entry?.metroLine}
            error={fieldErrors.metroLineId}
            required
          />
        ) : null}
        {isMetro ? <>
          <RemoteMultiSelect dictionary="metro-lines" label="Все линии станции"
            values={formState.lineIds} truncated filters={{ systemId: formState.systemId }}
            initialOptions={entry?.lines?.map((line) => ({ id: line.id, label: line.name })) ?? []}
            onChange={(values) => updateFormField('lineIds', values)} error={fieldErrors.lineIds} />
          <label className="developer-active-field"><input type="checkbox" checked={formState.locationIsInferred}
            onChange={(event) => updateFormField('locationIsInferred', event.target.checked)} />
            <span>Территория приблизительная, определена по системе метро</span></label>
          <p className="field-hint">Основная линия всегда входит в список линий. Если местоположение станции неизвестно, населённый пункт можно не указывать.</p>
        </> : null}

        {optionsQuery.data && Object.values(optionsQuery.data.truncated).some(
          Boolean,
        ) ? (
          <p className="field-hint">
            Введите текст в поле выбора. Остальные варианты подгружаются при прокрутке списка.
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
          <Notice as="p" tone="error" role="alert" className="form-error">{fieldErrors.form}</Notice>
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
            <Link
              className="button button--secondary"
              to={`/locations/${dictionaryKey}`}
            >
              Отмена
            </Link>
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
  const tableParameters = useTableParameters(searchParameters)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const sessionQuery = useQuery(sessionQueryOptions)
  const listQuery = useQuery({
    ...locationDictionaryListQueryOptions(dictionaryKey, tableParameters),
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
      window.setTimeout(() => restoreFocus(deleteTriggerRef.current), 0)
    },
  })

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
      ...(regionId && regionId !== searchParameters.get('regionId') ? { cityId: null, metroLineId: null } : {}),
      page: null,
    })
  }

  const updateCityFilter = (cityId: string) => {
    updateParameters({ cityId, ...(cityId && cityId !== searchParameters.get('cityId') ? { metroLineId: null } : {}), page: null })
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
    window.setTimeout(() => restoreFocus(deleteTriggerRef.current), 0)
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
  if (isEditing && sessionQuery.isError) return <ErrorState title="Не удалось проверить вход" isRetrying={sessionQuery.isFetching} onRetry={() => sessionQuery.refetch()} />
  if (listQuery.isError || !listQuery.data) {
    return <ErrorState onRetry={() => retryFailedQueries(listQuery, filterOptionsQuery, detailQuery)} />
  }
  if (filterOptionsQuery.isError || !filterOptionsQuery.data) {
    return <ErrorState onRetry={() => retryFailedQueries(filterOptionsQuery, listQuery, detailQuery)} />
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
    return <ErrorState onRetry={() => retryFailedQueries(detailQuery, listQuery, filterOptionsQuery)} />
  }

  const { results, page, totalCount, totalPages } = listQuery.data
  const options = filterOptionsQuery.data
  const isMetroDictionary = dictionaryKey.startsWith('metro')
  const showRegion = dictionaryKey === 'cities' || dictionaryKey === 'districts'
  const showCity = dictionaryKey === 'districts'
  const showMetroLine = dictionaryKey === 'metro'
  const showRegionColumn = showRegion && !showMetroLine

  return (
    <div className="page-stack location-dictionary-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Справочники</span>
          <h1>Локации</h1>
          <p>{configuration.description}</p>
        </div>
      </header>

      <Link className="button button--secondary" to="/locations/localities">Все населённые пункты и территории</Link>
      <SectionNavigation label="Справочники локаций" items={locationDictionaryConfigurations.map((item) => ({
        to: `/locations/${item.key}`, label: item.title,
      }))} />

      {sessionQuery.data?.capabilities.syncExternalData === true && !isMetroDictionary ? (
        <NationalLocationImportPanel />
      ) : null}
      {sessionQuery.data?.capabilities.syncExternalData === true && (!isMetroDictionary || showMetroLine) ? (
        <LocationImportPanel
          key={`${dictionaryKey}:${searchParameters.get('regionId')}:${searchParameters.get('cityId')}:${searchParameters.get('systemId')}`}
          dictionaryKey={dictionaryKey}
          regionId={searchParameters.get('regionId') ?? ''}
          cityId={searchParameters.get('cityId') ?? ''}
          systemId={searchParameters.get('systemId') ?? ''}
        />
      ) : null}

      <section
        className="filter-panel location-filter-panel"
        aria-label={`Фильтры: ${configuration.title}`}
      >
        <form className="search-form" role="search" onSubmit={(event) => event.preventDefault()}>
          <div className="live-search-control">
            <LiveFilterInput label="Поиск" id="location-search" parameter="q" placeholder="Название или связанная локация" />
          </div>
        </form>
        {showRegion ? (
          <RemoteSelect filter dictionary="regions" label="Регион" value={searchParameters.get('regionId') ?? ''}
            initialOptions={options.regions.map((option) => ({ id: option.id, label: option.name }))}
            onChange={(value) => updateRegionFilter(value)} />
        ) : null}
        {showCity ? (
          <RemoteSelect filter dictionary="cities" label="Город" value={searchParameters.get('cityId') ?? ''}
            initialOptions={options.cities.map((option) => ({ id: option.id, label: option.name }))}
            filters={{ regionId: searchParameters.get('regionId') }}
            onChange={(value) => updateCityFilter(value)} />
        ) : null}
        {showMetroLine ? (
          <RemoteSelect filter dictionary="metro-lines" label="Линия метро" value={searchParameters.get('metroLineId') ?? ''}
            truncated
            filters={{ systemId: searchParameters.get('systemId') }}
            onChange={(value) => updateParameters({
                metroLineId: value,
                page: null,
              })} />
        ) : null}
        {isMetroDictionary && dictionaryKey !== 'metro-systems' ? (
          <RemoteSelect filter dictionary="metro-systems" label="Система метро" truncated
            value={searchParameters.get('systemId') ?? ''}
            onChange={(value) => updateParameters({ systemId: value, metroLineId: null, page: null })} />
        ) : null}
        {isMetroDictionary && dictionaryKey !== 'metro-lines' ? (
          <RemoteSelect filter dictionary="locations" label={showMetroLine ? 'Населённый пункт станции' : 'Центр системы'} truncated
            filters={{ category: 'locality' }} value={searchParameters.get('locationId') ?? ''}
            onChange={(value) => updateParameters({ locationId: value, page: null })} />
        ) : null}
        <SelectFilter label="Статус" parameter="status" emptyLabel="Все"
          options={[{ value: 'active', label: 'Активные' }, { value: 'inactive', label: 'Неактивные' }]} />
        <ResetFilters />
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
              <TableScrollArea className="table-card property-table-wrapper" label={configuration.title}>
                <table className="property-table catalog-table location-table">
                  <caption className="visually-hidden">
                    {configuration.title}
                  </caption>
                  <thead>
                    <tr>
                      <SortableHeader field="name" defaultOrdering="default">{configuration.nameLabel}</SortableHeader>
                      {dictionaryKey === 'regions'
                        ? <SortableHeader field="code" defaultOrdering="default">Код</SortableHeader>
                        : null}
                      {showRegionColumn ? <SortableHeader field="region" defaultOrdering="default">Регион</SortableHeader> : null}
                      {showCity ? <SortableHeader field="city" defaultOrdering="default">Город</SortableHeader> : null}
                      {showMetroLine ? <SortableHeader field="metroLine" defaultOrdering="default">Линия</SortableHeader> : null}
                      {isMetroDictionary ? <><th scope="col">Система / линии</th><th scope="col">Территория</th></> : null}

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
                        {showRegionColumn
                          ? <td>{entry.region?.name ?? '—'}</td>
                          : null}
                        {showCity
                          ? <td>{entry.city?.name ?? '—'}</td>
                          : null}
                        {showMetroLine
                          ? <td><MetroLineLabel entry={entry} /></td>
                          : null}
                        {isMetroDictionary ? <><td>{entry.system?.name ?? '—'}{entry.lines?.length ? <p>{entry.lines.map((line) => line.name).join(', ')}</p> : null}
                          {entry.lineColor ? <span style={{ color: entry.lineColor }}>● {entry.lineColor}</span> : null}</td>
                          <td>{entry.location?.name ?? 'Не указана'}{entry.locationIsInferred ? <p className="field-hint">Приблизительно, по системе метро</p> : null}</td></> : null}

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
              </TableScrollArea>
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

                    </div>
                    <dl>
                      {isMetroDictionary ? <><div><dt>Система / линии</dt><dd>{entry.system?.name ?? '—'} {entry.lines?.map((line) => line.name).join(', ')}</dd></div>
                        <div><dt>Территория</dt><dd>{entry.location?.name ?? 'Не указана'}{entry.locationIsInferred ? ' (приблизительно)' : ''}</dd></div></> : null}
                      {entry.code ? (
                        <div><dt>Код</dt><dd>{entry.code}</dd></div>
                      ) : null}
                      {showRegionColumn && entry.region ? (
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
                    </dl>
                    {canManageCatalogs ? (
                      <div className="row-actions">
                        <Link
                          className="text-link"
                          to={`/locations/${dictionaryKey}/${entry.id}/edit`}
                        >
                          Редактировать
                        </Link>
                        <button
                          className="text-button text-button--danger"
                          type="button"
                          aria-label={`Удалить: ${entry.name}`}
                          onClick={(event) => openDeleteDialog(
                            entry,
                            event.currentTarget,
                          )}
                        >
                          Удалить
                        </button>
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </>
          )}

          {totalPages > 1 ? (
            <Pagination label={`Страницы: ${configuration.title}`} page={page} totalPages={totalPages} onPageChange={(nextPage) => updateParameters({ page: String(nextPage) })} />
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

      <p className="field-hint">
        Данные: <a href="https://github.com/hflabs/city" target="_blank" rel="noreferrer">HFLabs, CC BY-SA 4.0</a>;{' '}
        <a href="https://www.wikidata.org/wiki/Wikidata:Licensing" target="_blank" rel="noreferrer">Wikidata, CC0</a>;{' '}
        <a href="https://ru.wikipedia.org/wiki/Википедия:Условия_использования" target="_blank" rel="noreferrer">Википедия, CC BY-SA 4.0</a>.
        {' '}Ранее импортированные данные: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors, ODbL</a>.
      </p>

      {selectedEntry ? (
        <ModalDialog labelledBy="location-delete-title" describedBy="location-delete-description" pending={deleteMutation.isPending} onClose={closeDeleteDialog}>
            <span className="eyebrow">Подтверждение</span>
            <h2 id="location-delete-title">Удалить локацию?</h2>
            <p id="location-delete-description">
              «{selectedEntry.name}» будет удалена. Связанных записей:{' '}
              {formatInteger(selectedEntry.usageCount)}.
            </p>
            {deleteMutation.isError ? (
              <Notice as="p" tone="error" role="alert" className="form-error">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'Локация используется в других разделах и не может быть удалена.'
                  : 'Не удалось удалить локацию. Повторите попытку.'}
              </Notice>
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
          </ModalDialog>
      ) : null}
    </div>
  )
}
