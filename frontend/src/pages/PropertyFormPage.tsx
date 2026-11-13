import { Notice } from '@/shared/ui/Notice'
import { RemoteMultiSelect } from '@/shared/ui/RemoteMultiSelect'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  createProperty,
  propertyDetailQueryOptions,
  propertyFormOptionsQueryOptions,
  sessionQueryOptions,
  updateProperty,
} from '@/api/queries'
import type { PropertyDetail } from '@/api/schemas'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type PropertyFormState = {
  regionId: string
  cityId: string
  districtId: string
  developerId: string
  realEstateComplexId: string
  buildingId: string
  apartmentNumber: string
  layoutId: string
  decorationId: string
  area: string
  floor: string
  propertyCost: string
  windowViewIds: string[]
  clearLayoutImage: boolean
  clearFloorPlanImage: boolean
  clearWindowViewImage: boolean
}

type ImageFieldName = 'layoutImage' | 'floorPlanImage' | 'windowViewImage'
type ClearImageFieldName = (
  'clearLayoutImage' | 'clearFloorPlanImage' | 'clearWindowViewImage'
)
type FieldErrors = Record<string, string>

const emptyFormState: PropertyFormState = {
  regionId: '',
  cityId: '',
  districtId: '',
  developerId: '',
  realEstateComplexId: '',
  buildingId: '',
  apartmentNumber: '',
  layoutId: '',
  decorationId: '',
  area: '',
  floor: '',
  propertyCost: '',
  windowViewIds: [],
  clearLayoutImage: false,
  clearFloorPlanImage: false,
  clearWindowViewImage: false,
}

const imageFields: Array<{
  fieldName: ImageFieldName
  clearFieldName: ClearImageFieldName
  kind: PropertyDetail['images'][number]['kind']
  label: string
}> = [
  {
    fieldName: 'layoutImage',
    clearFieldName: 'clearLayoutImage',
    kind: 'layout',
    label: 'Планировка',
  },
  {
    fieldName: 'floorPlanImage',
    clearFieldName: 'clearFloorPlanImage',
    kind: 'floorPlan',
    label: 'План этажа',
  },
  {
    fieldName: 'windowViewImage',
    clearFieldName: 'clearWindowViewImage',
    kind: 'windowView',
    label: 'Вид из окна',
  },
]

function selectedIdentifier(value: string) {
  const identifier = Number(value)
  return Number.isInteger(identifier) && identifier > 0 ? identifier : null
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

export function PropertyFormPage() {
  const { propertyId } = useParams()
  const [searchParameters] = useSearchParams()
  const isEditing = propertyId !== undefined
  const propertyIdentifier = Number(propertyId ?? 0)
  const hasValidIdentifier = !isEditing || (
    Number.isInteger(propertyIdentifier) && propertyIdentifier > 0
  )
  const customerIdentifier = selectedIdentifier(
    searchParameters.get('customerId') ?? '',
  )
  const customerQuery = customerIdentifier
    ? `?customerId=${customerIdentifier}`
    : ''
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const initializedPropertyRef = useRef<number | null>(null)
  const sessionQuery = useQuery(sessionQueryOptions)
  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )
  const propertyQuery = useQuery({
    ...propertyDetailQueryOptions(propertyIdentifier),
    enabled: isEditing && hasValidIdentifier && canManageCatalogs,
  })
  const [formState, setFormState] = useState(emptyFormState)
  const [files, setFiles] = useState<Partial<Record<ImageFieldName, File>>>({})
  const optionsQuery = useQuery({
    ...propertyFormOptionsQueryOptions({
      regionId: selectedIdentifier(formState.regionId),
      cityId: selectedIdentifier(formState.cityId),
      districtId: selectedIdentifier(formState.districtId),
      developerId: selectedIdentifier(formState.developerId),
      realEstateComplexId: selectedIdentifier(
        formState.realEstateComplexId,
      ),
    }),
    enabled: hasValidIdentifier && canManageCatalogs,
  })
  const mutation = useMutation({
    mutationFn: (formData: FormData) => (
      isEditing
        ? updateProperty(propertyIdentifier, formData)
        : createProperty(formData)
    ),
    onSuccess: async (property) => {
      await queryClient.invalidateQueries({ queryKey: ['properties'] })
      await queryClient.invalidateQueries({ queryKey: ['overview'] })
      queryClient.setQueryData(['property', property.id], property)
      navigate(`/properties/${property.id}${customerQuery}`)
    },
  })
  const fieldErrors = extractFieldErrors(mutation.error)
  useDocumentTitle(isEditing ? 'Редактирование объекта' : 'Новый объект')

  useEffect(() => {
    const property = propertyQuery.data
    if (
      !isEditing
      || !property
      || initializedPropertyRef.current === property.id
    ) {
      return
    }
    setFormState({
      regionId: String(property.regionId),
      cityId: String(property.cityId),
      districtId: String(property.districtId),
      developerId: String(property.developerId),
      realEstateComplexId: String(property.realEstateComplexId),
      buildingId: String(property.buildingId),
      apartmentNumber: property.apartmentNumber,
      layoutId: String(property.layoutId),
      decorationId: String(property.decorationId),
      area: property.area,
      floor: String(property.floor),
      propertyCost: property.propertyCost,
      windowViewIds: property.windowViewIds.map(String),
      clearLayoutImage: false,
      clearFloorPlanImage: false,
      clearWindowViewImage: false,
    })
    initializedPropertyRef.current = property.id
  }, [isEditing, propertyQuery.data])

  const updateField = <FieldName extends keyof PropertyFormState>(
    fieldName: FieldName,
    value: PropertyFormState[FieldName],
  ) => {
    if (mutation.isError) mutation.reset()
    setFormState((current) => ({ ...current, [fieldName]: value }))
  }

  const updateRegion = (value: string) => {
    if (mutation.isError) mutation.reset()
    setFormState((current) => ({
      ...current,
      regionId: value,
      cityId: '',
      districtId: '',
      realEstateComplexId: '',
      buildingId: '',
    }))
  }

  const updateCity = (value: string) => {
    if (mutation.isError) mutation.reset()
    setFormState((current) => ({
      ...current,
      cityId: value,
      districtId: '',
      realEstateComplexId: '',
      buildingId: '',
    }))
  }

  const updateDistrict = (value: string) => {
    if (mutation.isError) mutation.reset()
    setFormState((current) => ({
      ...current,
      districtId: value,
      realEstateComplexId: '',
      buildingId: '',
    }))
  }

  const updateDeveloper = (value: string) => {
    if (mutation.isError) mutation.reset()
    setFormState((current) => ({
      ...current,
      developerId: value,
      realEstateComplexId: '',
      buildingId: '',
    }))
  }

  const updateComplex = (value: string) => {
    if (mutation.isError) mutation.reset()
    setFormState((current) => ({
      ...current,
      realEstateComplexId: value,
      buildingId: '',
    }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData()
    formData.append('apartmentNumber', formState.apartmentNumber)
    formData.append('buildingId', formState.buildingId)
    formData.append('decorationId', formState.decorationId)
    formData.append('layoutId', formState.layoutId)
    formData.append('area', formState.area)
    formData.append('floor', formState.floor)
    formData.append('propertyCost', formState.propertyCost)
    formData.append('replaceWindowViews', 'true')
    formState.windowViewIds.forEach((identifier) => {
      formData.append('windowViewIds', identifier)
    })
    imageFields.forEach(({ fieldName, clearFieldName }) => {
      const file = files[fieldName]
      if (file) formData.append(fieldName, file)
      if (formState[clearFieldName]) formData.append(clearFieldName, 'true')
    })
    mutation.mutate(formData)
  }

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Объект не найден"
        description="Проверьте адрес или вернитесь к каталогу недвижимости."
        action={(
          <Link className="button button--secondary" to="/properties">
            К каталогу
          </Link>
        )}
      />
    )
  }
  if (sessionQuery.isLoading) return <PageLoadingState />
  if (!canManageCatalogs) {
    return (
      <EmptyState
        title="Недостаточно прав"
        description="Создавать и редактировать объекты могут модераторы каталога."
        action={(
          <Link className="button button--secondary" to="/properties">
            К каталогу
          </Link>
        )}
      />
    )
  }
  if (isEditing && propertyQuery.isLoading) return <PageLoadingState />
  if (isEditing && (propertyQuery.isError || !propertyQuery.data)) {
    return (
      <ErrorState
        title="Объект не найден или недоступен"
        onRetry={() => void propertyQuery.refetch()}
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
  const property = propertyQuery.data
  const cancelPath = isEditing
    ? `/properties/${propertyIdentifier}${customerQuery}`
    : `/properties${customerQuery}`
  const hasGeneralError = mutation.isError && (
    Object.keys(fieldErrors).length === 0
    || Boolean(fieldErrors.non_field_errors)
    || Boolean(fieldErrors.detail)
  )

  return (
    <div className="page-stack property-form-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Управление каталогом</span>
          <h1>{isEditing ? 'Редактирование объекта' : 'Новый объект'}</h1>
          <p>
            Выберите локацию по порядку, затем заполните параметры квартиры
            и при необходимости добавьте изображения.
          </p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to={cancelPath}>
            Отмена
          </Link>
        </div>
      </header>

      {hasTruncatedOptions ? (
        <Notice as="p" tone="info" role="status" className="status-notice">
            Для поиска остальных значений используйте поле поиска в справочнике или кнопку «Показать ещё варианты».
          </Notice>
      ) : null}
      {optionsQuery.isFetching ? (
        <Notice as="p" tone="info" role="status" className="customer-form-loading">
          Обновляем связанные справочники…
        </Notice>
      ) : null}

      <form className="customer-form property-form" onSubmit={handleSubmit}>
        <section
          className="customer-form-section"
          aria-labelledby="property-location-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">01</span>
            <div>
              <h2 id="property-location-section">Локация</h2>
              <p>Регион, адресная и девелоперская иерархия объекта.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <RemoteSelect
              dictionary="regions" label={"Регион"}
              value={formState.regionId} onChange={(value) => updateRegion(value)}
              initialOptions={(options.regions ?? []).map((option) => ({ id: option.id, label: option.name }))}
              truncated={options.truncated.regions}
              required
            />
            <RemoteSelect
              dictionary="cities" label={"Город"}
              value={formState.cityId} onChange={(value) => updateCity(value)}
              initialOptions={(options.cities ?? []).map((option) => ({ id: option.id, label: option.name }))}
              truncated={options.truncated.cities}
              filters={{ regionId: formState.regionId }}
              disabled={!formState.regionId}
              required
            />
            <RemoteSelect
              dictionary="districts" label={"Район"}
              value={formState.districtId} onChange={(value) => updateDistrict(value)}
              initialOptions={(options.districts ?? []).map((option) => ({ id: option.id, label: option.name }))}
              truncated={options.truncated.districts}
              filters={{ cityId: formState.cityId }}
              disabled={!formState.cityId}
              required
            />
            <RemoteSelect
              dictionary="developers" label={"Застройщик"}
              value={formState.developerId} onChange={(value) => updateDeveloper(value)}
              initialOptions={(options.developers ?? []).map((option) => ({ id: option.id, label: option.label }))}
              truncated={options.truncated.developers}
              required
            />
            <RemoteSelect
              dictionary="complexes" label={"Жилой комплекс"}
              value={formState.realEstateComplexId} onChange={(value) => updateComplex(value)}
              initialOptions={(options.realEstateComplexes ?? []).map((option) => ({ id: option.id, label: option.name }))}
              truncated={options.truncated.realEstateComplexes}
              filters={{ districtId: formState.districtId, developerId: formState.developerId }}
              disabled={!formState.districtId || !formState.developerId}
              required
            />
            <RemoteSelect
              dictionary="buildings" label={"Корпус"}
              value={formState.buildingId} onChange={(value) => updateField('buildingId', value)}
              initialOptions={(options.buildings ?? []).map((option) => ({ id: option.id, label: option.number }))}
              truncated={options.truncated.buildings}
              filters={{ realEstateComplexId: formState.realEstateComplexId }}
              disabled={!formState.realEstateComplexId}
              error={fieldErrors.buildingId}
              required
            />
          </div>
        </section>

        <section
          className="customer-form-section"
          aria-labelledby="property-parameters-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">02</span>
            <div>
              <h2 id="property-parameters-section">Параметры квартиры</h2>
              <p>Номер, площадь, этаж, стоимость и характеристики отделки.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field">
              Номер квартиры *
              <input
                name="apartmentNumber"
                value={formState.apartmentNumber}
                onChange={(event) => updateField('apartmentNumber', event.target.value)}
                maxLength={50}
                required
                aria-invalid={Boolean(fieldErrors.apartmentNumber)}
                aria-describedby={fieldErrors.apartmentNumber ? 'apartmentNumber-error' : undefined}
              />
              <FieldError fieldName="apartmentNumber" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Площадь, м² *
              <input
                name="area"
                type="number"
                step="0.01"
                value={formState.area}
                onChange={(event) => updateField('area', event.target.value)}
                required
                aria-invalid={Boolean(fieldErrors.area)}
                aria-describedby={fieldErrors.area ? 'area-error' : undefined}
              />
              <FieldError fieldName="area" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Этаж *
              <input
                name="floor"
                type="number"
                step="1"
                value={formState.floor}
                onChange={(event) => updateField('floor', event.target.value)}
                required
                aria-invalid={Boolean(fieldErrors.floor)}
                aria-describedby={fieldErrors.floor ? 'floor-error' : undefined}
              />
              <FieldError fieldName="floor" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Стоимость, ₽ *
              <input
                name="propertyCost"
                type="number"
                step="0.01"
                value={formState.propertyCost}
                onChange={(event) => updateField('propertyCost', event.target.value)}
                required
                aria-invalid={Boolean(fieldErrors.propertyCost)}
                aria-describedby={fieldErrors.propertyCost ? 'propertyCost-error' : undefined}
              />
              <FieldError fieldName="propertyCost" errors={fieldErrors} />
            </label>
            <RemoteSelect
              dictionary="layouts" label={"Планировка"}
              value={formState.layoutId} onChange={(value) => updateField('layoutId', value)}
              initialOptions={(options.layouts ?? []).map((option) => ({ id: option.id, label: option.name }))}
              truncated={options.truncated.layouts}
              error={fieldErrors.layoutId}
              required
            />
            <RemoteSelect
              dictionary="decorations" label={"Отделка"}
              value={formState.decorationId} onChange={(value) => updateField('decorationId', value)}
              initialOptions={(options.decorations ?? []).map((option) => ({ id: option.id, label: option.name }))}
              truncated={options.truncated.decorations}
              error={fieldErrors.decorationId}
              required
            />
          </div>
        </section>

        <section
          className="customer-form-section"
          aria-labelledby="property-materials-section"
        >
          <div className="customer-form-section__heading">
            <span aria-hidden="true">03</span>
            <div>
              <h2 id="property-materials-section">Виды и изображения</h2>
              <p>Дополнительные характеристики и визуальные материалы.</p>
            </div>
          </div>
          <RemoteMultiSelect dictionary="window-views" label="Вид из окна"
              values={formState.windowViewIds} onChange={(values) => updateField('windowViewIds', values)}
              initialOptions={options.windowViews.map((option) => ({ id: option.id, label: option.name }))}
              truncated={options.truncated.windowViews} error={fieldErrors.windowViewIds} />

          <div className="property-upload-grid">
            {imageFields.map((imageField) => {
              const currentImage = property?.images.find(
                (image) => image.kind === imageField.kind,
              )
              const isCleared = formState[imageField.clearFieldName]
              return (
                <div className="property-upload-card" key={imageField.fieldName}>
                  <h3>{imageField.label}</h3>
                  {currentImage?.url && !isCleared ? (
                    <div className="property-upload-current">
                      <img src={currentImage.url} alt="" />
                      <a href={currentImage.url} target="_blank" rel="noreferrer">
                        Открыть текущее
                      </a>
                    </div>
                  ) : null}
                  {currentImage?.url ? (
                    <button
                      className="text-button"
                      type="button"
                      onClick={() => updateField(
                        imageField.clearFieldName,
                        !isCleared,
                      )}
                    >
                      {isCleared ? 'Отменить удаление' : 'Удалить текущее'}
                    </button>
                  ) : null}
                  {isCleared ? (
                    <Notice as="p" tone="info" role="status" className="property-upload-note">
                      Текущее изображение будет удалено после сохранения.
                    </Notice>
                  ) : null}
                  <label className="form-field">
                    {currentImage?.url ? 'Заменить файлом' : 'Загрузить файл'}
                    <input
                      type="file"
                      accept="image/gif,image/jpeg,image/png,image/webp"
                      onChange={(event) => {
                        const file = event.target.files?.[0]
                        setFiles((current) => ({
                          ...current,
                          [imageField.fieldName]: file,
                        }))
                        if (mutation.isError) mutation.reset()
                      }}
                      aria-invalid={Boolean(fieldErrors[imageField.fieldName])}
                      aria-describedby={
                        fieldErrors[imageField.fieldName]
                          ? `${imageField.fieldName}-error`
                          : undefined
                      }
                    />
                    <FieldError
                      fieldName={imageField.fieldName}
                      errors={fieldErrors}
                    />
                  </label>
                </div>
              )
            })}
          </div>
        </section>

        {hasGeneralError ? (
          <Notice as="p" tone="error" role="alert" className="form-error">
            {fieldErrors.non_field_errors
              || fieldErrors.detail
              || 'Не удалось сохранить объект. Проверьте данные и повторите попытку.'}
          </Notice>
        ) : null}
        <div className="customer-form-actions">
          <Link className="button button--secondary" to={cancelPath}>
            Отмена
          </Link>
          <button
            className="button button--primary"
            type="submit"
            disabled={mutation.isPending}
          >
            {mutation.isPending
              ? 'Сохраняем…'
              : isEditing ? 'Сохранить изменения' : 'Создать объект'}
          </button>
        </div>
      </form>
    </div>
  )
}
