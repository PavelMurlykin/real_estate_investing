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

  const updateWindowView = (value: string, isChecked: boolean) => {
    const nextValues = isChecked
      ? [...formState.windowViewIds, value]
      : formState.windowViewIds.filter((item) => item !== value)
    updateField('windowViewIds', nextValues)
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
  const legacyFormUrl = isEditing && property
    ? property.legacyEditUrl
    : '/property/create/'
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
          <a className="button button--secondary" href={legacyFormUrl}>
            Django-форма
          </a>
        </div>
      </header>

      {hasTruncatedOptions ? (
        <p className="status-notice" role="status">
          Один из справочников показан частично. Полный список доступен в
          сохранённой Django-форме.
        </p>
      ) : null}
      {optionsQuery.isFetching ? (
        <p className="customer-form-loading" role="status">
          Обновляем связанные справочники…
        </p>
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
            <label className="form-field">
              Регион *
              <select
                value={formState.regionId}
                onChange={(event) => updateRegion(event.target.value)}
                required
              >
                <option value="">Выберите регион</option>
                {options.regions.map((option) => (
                  <option value={option.id} key={option.id}>{option.name}</option>
                ))}
              </select>
            </label>
            <label className="form-field">
              Город *
              <select
                value={formState.cityId}
                onChange={(event) => updateCity(event.target.value)}
                disabled={!formState.regionId}
                required
              >
                <option value="">Выберите город</option>
                {options.cities.map((option) => (
                  <option value={option.id} key={option.id}>{option.name}</option>
                ))}
              </select>
            </label>
            <label className="form-field">
              Район *
              <select
                value={formState.districtId}
                onChange={(event) => updateDistrict(event.target.value)}
                disabled={!formState.cityId}
                required
              >
                <option value="">Выберите район</option>
                {options.districts.map((option) => (
                  <option value={option.id} key={option.id}>{option.name}</option>
                ))}
              </select>
            </label>
            <label className="form-field">
              Застройщик *
              <select
                value={formState.developerId}
                onChange={(event) => updateDeveloper(event.target.value)}
                required
              >
                <option value="">Выберите застройщика</option>
                {options.developers.map((option) => (
                  <option value={option.id} key={option.id}>{option.label}</option>
                ))}
              </select>
            </label>
            <label className="form-field">
              Жилой комплекс *
              <select
                value={formState.realEstateComplexId}
                onChange={(event) => updateComplex(event.target.value)}
                disabled={!formState.districtId || !formState.developerId}
                required
              >
                <option value="">Выберите ЖК</option>
                {options.realEstateComplexes.map((option) => (
                  <option value={option.id} key={option.id}>{option.name}</option>
                ))}
              </select>
            </label>
            <label className="form-field">
              Корпус *
              <select
                name="buildingId"
                value={formState.buildingId}
                onChange={(event) => updateField('buildingId', event.target.value)}
                disabled={!formState.realEstateComplexId}
                required
                aria-invalid={Boolean(fieldErrors.buildingId)}
                aria-describedby={fieldErrors.buildingId ? 'buildingId-error' : undefined}
              >
                <option value="">Выберите корпус</option>
                {options.buildings.map((option) => (
                  <option value={option.id} key={option.id}>{option.number}</option>
                ))}
              </select>
              <FieldError fieldName="buildingId" errors={fieldErrors} />
            </label>
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
            <label className="form-field">
              Планировка *
              <select
                name="layoutId"
                value={formState.layoutId}
                onChange={(event) => updateField('layoutId', event.target.value)}
                required
                aria-invalid={Boolean(fieldErrors.layoutId)}
                aria-describedby={fieldErrors.layoutId ? 'layoutId-error' : undefined}
              >
                <option value="">Выберите планировку</option>
                {options.layouts.map((option) => (
                  <option value={option.id} key={option.id}>{option.name}</option>
                ))}
              </select>
              <FieldError fieldName="layoutId" errors={fieldErrors} />
            </label>
            <label className="form-field">
              Отделка *
              <select
                name="decorationId"
                value={formState.decorationId}
                onChange={(event) => updateField('decorationId', event.target.value)}
                required
                aria-invalid={Boolean(fieldErrors.decorationId)}
                aria-describedby={fieldErrors.decorationId ? 'decorationId-error' : undefined}
              >
                <option value="">Выберите отделку</option>
                {options.decorations.map((option) => (
                  <option value={option.id} key={option.id}>{option.name}</option>
                ))}
              </select>
              <FieldError fieldName="decorationId" errors={fieldErrors} />
            </label>
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
          <fieldset className="customer-choice-field property-window-views">
            <legend>Вид из окна</legend>
            <div className="customer-choice-grid customer-choice-grid--compact">
              {options.windowViews.map((option) => (
                <label key={option.id}>
                  <input
                    type="checkbox"
                    checked={formState.windowViewIds.includes(String(option.id))}
                    onChange={(event) => updateWindowView(
                      String(option.id),
                      event.target.checked,
                    )}
                  />
                  <span>{option.name}</span>
                </label>
              ))}
            </div>
            <FieldError fieldName="windowViewIds" errors={fieldErrors} />
          </fieldset>

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
                    <p className="property-upload-note" role="status">
                      Текущее изображение будет удалено после сохранения.
                    </p>
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
          <p className="form-error" role="alert">
            {fieldErrors.non_field_errors
              || fieldErrors.detail
              || 'Не удалось сохранить объект. Проверьте данные и повторите попытку.'}
          </p>
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
