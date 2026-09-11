import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  createRealEstateComplex,
  realEstateComplexDetailQueryOptions,
  realEstateComplexOptionsQueryOptions,
  sessionQueryOptions,
  updateRealEstateComplex,
} from '@/api/queries'
import { RealEstateComplexBuildingEditor } from '@/features/realEstateComplex/RealEstateComplexBuildingEditor'
import { RealEstateComplexMetroEditor } from '@/features/realEstateComplex/RealEstateComplexMetroEditor'
import {
  createBuildingRowsFromDetail,
  createEmptyBuildingRow,
  createEmptyMetroRow,
  createMetroRowsFromDetail,
} from '@/features/realEstateComplex/formTypes'
import type {
  BuildingFormRow,
  MetroAvailabilityFormRow,
} from '@/features/realEstateComplex/formTypes'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type ComplexFormState = {
  name: string
  description: string
  developerId: string
  regionId: string
  cityId: string
  districtId: string
  realEstateClassId: string
  realEstateTypeId: string
  mapLink: string
  presentationLink: string
  investmentPotential: string
  isActive: boolean
}

type FieldErrors = Record<string, string>

const emptyFormState: ComplexFormState = {
  name: '',
  description: '',
  developerId: '',
  regionId: '',
  cityId: '',
  districtId: '',
  realEstateClassId: '',
  realEstateTypeId: '',
  mapLink: '',
  presentationLink: '',
  investmentPotential: '',
  isActive: true,
}

function selectedIdentifier(value: string) {
  const identifier = Number(value)
  return Number.isInteger(identifier) && identifier > 0 ? identifier : null
}

function optionalInteger(value: string) {
  return value ? Number(value) : null
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
  if (!(error instanceof ApiError) || !error.details
    || typeof error.details !== 'object' || Array.isArray(error.details)) {
    return { form: 'Не удалось сохранить жилой комплекс. Повторите попытку.' }
  }
  const errors: FieldErrors = {}
  Object.entries(error.details).forEach(([fieldName, value]) => {
    const message = findFirstError(value)
    if (message) errors[fieldName] = message
  })
  return Object.keys(errors).length
    ? errors
    : { form: 'Не удалось сохранить жилой комплекс. Повторите попытку.' }
}

function validateForm(
  formState: ComplexFormState,
  buildingRows: BuildingFormRow[],
  metroRows: MetroAvailabilityFormRow[],
) {
  const errors: FieldErrors = {}
  if (!formState.name.trim()) errors.name = 'Укажите название ЖК.'
  if (!formState.developerId) errors.developerId = 'Выберите застройщика.'
  if (!formState.regionId) errors.regionId = 'Выберите регион.'
  if (!formState.cityId) errors.cityId = 'Выберите город.'
  if (!formState.districtId) errors.districtId = 'Выберите район.'
  if (!formState.realEstateClassId) {
    errors.realEstateClassId = 'Выберите класс ЖК.'
  }
  if (!formState.realEstateTypeId) {
    errors.realEstateTypeId = 'Выберите тип недвижимости.'
  }
  const buildingNumbers = buildingRows.map((row) => row.number.trim().toLowerCase())
  if (buildingRows.some((row) => !row.number.trim())) {
    errors.buildings = 'У каждого корпуса должен быть номер.'
  } else if (new Set(buildingNumbers).size !== buildingNumbers.length) {
    errors.buildings = 'Номера корпусов не должны повторяться.'
  } else if (buildingRows.some((row) => (
    Boolean(row.commissioningYear) !== Boolean(row.commissioningQuarter)
    || Boolean(row.keyHandoverYear) !== Boolean(row.keyHandoverQuarter)
  ))) {
    errors.buildings = 'Для квартального срока укажите год и квартал.'
  }
  const metroIdentifiers = metroRows.map((row) => row.metroId)
  if (metroRows.some((row) => (
    !row.metroId
    || !row.transportAccessibilityTypeId
    || Number(row.walkingTimeMinutes) <= 0
  ))) {
    errors.metroAvailability = 'Заполните станцию, способ и время для каждой строки.'
  } else if (new Set(metroIdentifiers).size !== metroIdentifiers.length) {
    errors.metroAvailability = 'Одна станция не может быть добавлена дважды.'
  }
  return errors
}

function FieldError({ id, message }: { id: string, message?: string }) {
  return message
    ? <span className="field-error" id={id}>{message}</span>
    : null
}

export function RealEstateComplexFormPage() {
  const { complexId = '' } = useParams()
  const complexIdentifier = Number(complexId)
  const isEditing = complexId !== ''
  const hasValidIdentifier = !isEditing || (
    Number.isInteger(complexIdentifier) && complexIdentifier > 0
  )
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const sessionQuery = useQuery(sessionQueryOptions)
  const complexQuery = useQuery({
    ...realEstateComplexDetailQueryOptions(complexIdentifier),
    enabled: isEditing && hasValidIdentifier,
  })
  const [formState, setFormState] = useState(emptyFormState)
  const [buildingRows, setBuildingRows] = useState<BuildingFormRow[]>([
    createEmptyBuildingRow(),
  ])
  const [metroRows, setMetroRows] = useState<MetroAvailabilityFormRow[]>([])
  const [photo, setPhoto] = useState<File | null>(null)
  const [clearPhoto, setClearPhoto] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const hasInitialized = useRef(false)
  const selectedRegionIdentifier = selectedIdentifier(formState.regionId)
  const selectedCityIdentifier = selectedIdentifier(formState.cityId)
  const optionsQuery = useQuery(realEstateComplexOptionsQueryOptions({
    regionId: selectedRegionIdentifier,
    cityId: selectedCityIdentifier,
  }))
  const mutation = useMutation({
    mutationFn: (formData: FormData) => isEditing
      ? updateRealEstateComplex(complexIdentifier, formData)
      : createRealEstateComplex(formData),
    onSuccess: async (savedComplex) => {
      await queryClient.invalidateQueries({
        queryKey: ['real-estate-complexes'],
      })
      await queryClient.invalidateQueries({ queryKey: ['overview'] })
      queryClient.setQueryData(
        ['real-estate-complex', savedComplex.id],
        savedComplex,
      )
      navigate(`/complexes/${savedComplex.id}`)
    },
    onError: (error) => setFieldErrors(parseApiErrors(error)),
  })
  useDocumentTitle(isEditing ? 'Редактирование ЖК' : 'Новый жилой комплекс')

  useEffect(() => {
    if (!isEditing || !complexQuery.data || hasInitialized.current) return
    const realEstateComplex = complexQuery.data
    setFormState({
      name: realEstateComplex.name,
      description: realEstateComplex.description ?? '',
      developerId: realEstateComplex.developerId.toString(),
      regionId: realEstateComplex.regionId.toString(),
      cityId: realEstateComplex.cityId.toString(),
      districtId: realEstateComplex.districtId.toString(),
      realEstateClassId: realEstateComplex.realEstateClassId.toString(),
      realEstateTypeId: realEstateComplex.realEstateTypeId.toString(),
      mapLink: realEstateComplex.mapUrl ?? '',
      presentationLink: realEstateComplex.presentationUrl ?? '',
      investmentPotential: realEstateComplex.investmentPotential ?? '',
      isActive: realEstateComplex.isActive,
    })
    setBuildingRows(createBuildingRowsFromDetail(realEstateComplex))
    setMetroRows(createMetroRowsFromDetail(realEstateComplex))
    hasInitialized.current = true
  }, [complexQuery.data, isEditing])

  const updateField = <FieldName extends keyof ComplexFormState>(
    fieldName: FieldName,
    value: ComplexFormState[FieldName],
  ) => {
    setFormState((current) => ({ ...current, [fieldName]: value }))
    setFieldErrors((current) => ({ ...current, [fieldName]: '' }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const errors = validateForm(formState, buildingRows, metroRows)
    setFieldErrors(errors)
    if (Object.keys(errors).length) return

    const formData = new FormData()
    formData.append('name', formState.name.trim())
    formData.append('description', formState.description.trim())
    formData.append('developerId', formState.developerId)
    formData.append('districtId', formState.districtId)
    formData.append('realEstateClassId', formState.realEstateClassId)
    formData.append('realEstateTypeId', formState.realEstateTypeId)
    formData.append('mapLink', formState.mapLink.trim())
    formData.append('presentationLink', formState.presentationLink.trim())
    formData.append('investmentPotential', formState.investmentPotential.trim())
    formData.append('isActive', String(formState.isActive))
    formData.append('buildings', JSON.stringify(buildingRows.map((row) => ({
      ...(row.id ? { id: row.id } : {}),
      number: row.number.trim(),
      address: row.address.trim() || null,
      commissioningDate: row.commissioningDate || null,
      commissioningYear: optionalInteger(row.commissioningYear),
      commissioningQuarter: optionalInteger(row.commissioningQuarter),
      keyHandoverDate: row.keyHandoverDate || null,
      keyHandoverYear: optionalInteger(row.keyHandoverYear),
      keyHandoverQuarter: optionalInteger(row.keyHandoverQuarter),
      isActive: row.isActive,
    }))))
    formData.append('metroAvailability', JSON.stringify(metroRows.map((row) => ({
      ...(row.id ? { id: row.id } : {}),
      metroId: Number(row.metroId),
      transportAccessibilityTypeId: Number(
        row.transportAccessibilityTypeId,
      ),
      walkingTimeMinutes: Number(row.walkingTimeMinutes),
      isActive: row.isActive,
    }))))
    if (photo) formData.append('photo', photo)
    if (clearPhoto) formData.append('clearPhoto', 'true')
    mutation.mutate(formData)
  }

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Жилой комплекс не найден"
        description="Проверьте адрес страницы и вернитесь к списку."
        action={<Link className="button button--secondary" to="/complexes">К списку</Link>}
      />
    )
  }
  if (sessionQuery.isLoading || (isEditing && complexQuery.isLoading)) {
    return <PageLoadingState />
  }
  if (!sessionQuery.data?.capabilities.manageCatalogs) {
    return (
      <EmptyState
        title="Недостаточно прав"
        description="Создавать и изменять жилые комплексы могут только модераторы."
        action={<Link className="button button--secondary" to="/complexes">К списку</Link>}
      />
    )
  }
  if ((isEditing && (complexQuery.isError || !complexQuery.data))
    || optionsQuery.isError) {
    return <ErrorState onRetry={() => {
      void complexQuery.refetch()
      void optionsQuery.refetch()
    }} />
  }
  if (optionsQuery.isLoading || !optionsQuery.data) return <PageLoadingState />

  const options = optionsQuery.data
  const existingPhotoUrl = complexQuery.data?.photoUrl ?? null
  const optionsTruncated = Object.values(options.truncated).some(Boolean)

  return (
    <div className="page-stack complex-form-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Недвижимость</span>
          <h1>{isEditing ? 'Редактирование ЖК' : 'Новый жилой комплекс'}</h1>
          <p>Основные сведения, локация, корпуса и доступность метро.</p>
        </div>
        <div className="page-header__actions">
          {isEditing && complexQuery.data ? (
            <a
              className="button button--secondary"
              href={complexQuery.data.legacyEditUrl}
            >
              Django-форма
            </a>
          ) : null}
          <Link className="button button--secondary" to="/complexes">
            Отмена
          </Link>
        </div>
      </header>

      <form className="customer-form complex-form" noValidate onSubmit={handleSubmit}>
        <section className="customer-form-section complex-form-section">
          <div className="customer-form-section__heading">
            <span aria-hidden="true">01</span>
            <div>
              <h2>Основные сведения</h2>
              <p>Название, застройщик, класс и описание проекта.</p>
            </div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field" htmlFor="complex-name">
              Название ЖК *
              <input
                id="complex-name"
                value={formState.name}
                maxLength={255}
                aria-invalid={Boolean(fieldErrors.name)}
                aria-describedby={fieldErrors.name ? 'complex-name-error' : undefined}
                onChange={(event) => updateField('name', event.target.value)}
              />
              <FieldError id="complex-name-error" message={fieldErrors.name} />
            </label>
            <label className="form-field" htmlFor="complex-developer-field">
              Застройщик *
              <select
                id="complex-developer-field"
                value={formState.developerId}
                aria-invalid={Boolean(fieldErrors.developerId)}
                onChange={(event) => updateField('developerId', event.target.value)}
              >
                <option value="">Выберите застройщика</option>
                {options.developers.map((developer) => (
                  <option key={developer.id} value={developer.id}>{developer.label}</option>
                ))}
              </select>
              <FieldError id="complex-developer-error" message={fieldErrors.developerId} />
            </label>
            <label className="form-field" htmlFor="complex-class-field">
              Класс ЖК *
              <select
                id="complex-class-field"
                value={formState.realEstateClassId}
                aria-invalid={Boolean(fieldErrors.realEstateClassId)}
                onChange={(event) => updateField('realEstateClassId', event.target.value)}
              >
                <option value="">Выберите класс</option>
                {options.realEstateClasses.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
              <FieldError id="complex-class-error" message={fieldErrors.realEstateClassId} />
            </label>
            <label className="form-field" htmlFor="complex-type-field">
              Тип недвижимости *
              <select
                id="complex-type-field"
                value={formState.realEstateTypeId}
                aria-invalid={Boolean(fieldErrors.realEstateTypeId)}
                onChange={(event) => updateField('realEstateTypeId', event.target.value)}
              >
                <option value="">Выберите тип</option>
                {options.realEstateTypes.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
              <FieldError id="complex-type-error" message={fieldErrors.realEstateTypeId} />
            </label>
            <label className="form-field form-field--wide" htmlFor="complex-description">
              Описание
              <textarea
                id="complex-description"
                value={formState.description}
                onChange={(event) => updateField('description', event.target.value)}
              />
            </label>
            <label className="form-field form-field--wide" htmlFor="complex-investment">
              Инвестиционный потенциал
              <textarea
                id="complex-investment"
                value={formState.investmentPotential}
                onChange={(event) => updateField('investmentPotential', event.target.value)}
              />
            </label>
            <label className="developer-active-field form-field--wide">
              <input
                type="checkbox"
                checked={formState.isActive}
                onChange={(event) => updateField('isActive', event.target.checked)}
              />
              <span>
                ЖК активен
                <small>Неактивные записи остаются в справочнике.</small>
              </span>
            </label>
          </div>
        </section>

        <section className="customer-form-section complex-form-section">
          <div className="customer-form-section__heading">
            <span aria-hidden="true">02</span>
            <div><h2>Локация и материалы</h2><p>Адресная и презентационная информация.</p></div>
          </div>
          <div className="field-grid customer-form-grid">
            <label className="form-field" htmlFor="complex-region-field">
              Регион *
              <select
                id="complex-region-field"
                value={formState.regionId}
                aria-invalid={Boolean(fieldErrors.regionId)}
                onChange={(event) => {
                  setFormState((current) => ({
                    ...current,
                    regionId: event.target.value,
                    cityId: '',
                    districtId: '',
                  }))
                  setMetroRows([])
                  setFieldErrors((current) => ({
                    ...current,
                    regionId: '',
                    cityId: '',
                    districtId: '',
                    metroAvailability: '',
                  }))
                }}
              >
                <option value="">Выберите регион</option>
                {options.regions.map((region) => (
                  <option key={region.id} value={region.id}>{region.name}</option>
                ))}
              </select>
              <FieldError id="complex-region-error" message={fieldErrors.regionId} />
            </label>
            <label className="form-field" htmlFor="complex-city-field">
              Город *
              <select
                id="complex-city-field"
                value={formState.cityId}
                disabled={!formState.regionId}
                aria-invalid={Boolean(fieldErrors.cityId)}
                onChange={(event) => {
                  setFormState((current) => ({
                    ...current,
                    cityId: event.target.value,
                    districtId: '',
                  }))
                  setMetroRows([])
                  setFieldErrors((current) => ({
                    ...current,
                    cityId: '',
                    districtId: '',
                    metroAvailability: '',
                  }))
                }}
              >
                <option value="">Выберите город</option>
                {options.cities.map((city) => (
                  <option key={city.id} value={city.id}>{city.name}</option>
                ))}
              </select>
              <FieldError id="complex-city-error" message={fieldErrors.cityId} />
            </label>
            <label className="form-field" htmlFor="complex-district-field">
              Район *
              <select
                id="complex-district-field"
                value={formState.districtId}
                disabled={!formState.cityId}
                aria-invalid={Boolean(fieldErrors.districtId)}
                onChange={(event) => updateField('districtId', event.target.value)}
              >
                <option value="">Выберите район</option>
                {options.districts.map((district) => (
                  <option key={district.id} value={district.id}>{district.name}</option>
                ))}
              </select>
              <FieldError id="complex-district-error" message={fieldErrors.districtId} />
            </label>
            <label className="form-field" htmlFor="complex-map-link">
              Ссылка на карте
              <input
                id="complex-map-link"
                type="url"
                value={formState.mapLink}
                placeholder="https://"
                onChange={(event) => updateField('mapLink', event.target.value)}
              />
            </label>
            <label className="form-field" htmlFor="complex-presentation-link">
              Ссылка на презентацию
              <input
                id="complex-presentation-link"
                type="url"
                value={formState.presentationLink}
                placeholder="https://"
                onChange={(event) => updateField('presentationLink', event.target.value)}
              />
            </label>
            <div className="property-upload-card complex-photo-upload form-field--wide">
              <h3>Фото ЖК</h3>
              {existingPhotoUrl && !clearPhoto ? (
                <div className="property-upload-current">
                  <img src={existingPhotoUrl} alt="Текущее фото ЖК" />
                  <button
                    className="text-button text-button--danger"
                    type="button"
                    onClick={() => setClearPhoto(true)}
                  >
                    Удалить текущее
                  </button>
                </div>
              ) : null}
              <label className="form-field" htmlFor="complex-photo-field">
                Новый файл
                <input
                  id="complex-photo-field"
                  type="file"
                  accept="image/jpeg,image/png,image/gif,image/webp"
                  onChange={(event) => {
                    setPhoto(event.target.files?.[0] ?? null)
                    if (event.target.files?.[0]) setClearPhoto(false)
                  }}
                />
              </label>
              <FieldError id="complex-photo-error" message={fieldErrors.photo} />
            </div>
          </div>
        </section>

        <RealEstateComplexBuildingEditor
          rows={buildingRows}
          quarters={options.quarters}
          error={fieldErrors.buildings}
          onAdd={() => setBuildingRows((current) => [
            ...current,
            createEmptyBuildingRow(),
          ])}
          onChange={(index, row) => setBuildingRows((current) => (
            current.map((item, itemIndex) => itemIndex === index ? row : item)
          ))}
          onRemove={(index) => setBuildingRows((current) => (
            current.filter((_item, itemIndex) => itemIndex !== index)
          ))}
        />
        <RealEstateComplexMetroEditor
          rows={metroRows}
          options={options}
          error={fieldErrors.metroAvailability}
          onAdd={() => setMetroRows((current) => [
            ...current,
            createEmptyMetroRow(),
          ])}
          onChange={(index, row) => setMetroRows((current) => (
            current.map((item, itemIndex) => itemIndex === index ? row : item)
          ))}
          onRemove={(index) => setMetroRows((current) => (
            current.filter((_item, itemIndex) => itemIndex !== index)
          ))}
        />

        {optionsTruncated ? (
          <p className="filter-panel__notice" role="status">
            Часть крупных справочников ограничена. Полный перечень доступен
            в прежней версии.
          </p>
        ) : null}
        {fieldErrors.form ? (
          <p className="form-error" role="alert">{fieldErrors.form}</p>
        ) : null}
        <div className="customer-form-actions">
          <button
            className="button button--primary"
            type="submit"
            disabled={mutation.isPending}
          >
            {mutation.isPending
              ? 'Сохраняем…'
              : isEditing ? 'Сохранить изменения' : 'Создать ЖК'}
          </button>
          <Link className="button button--secondary" to="/complexes">
            Отмена
          </Link>
        </div>
      </form>
    </div>
  )
}
