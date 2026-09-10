import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import {
  propertyDetailQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type { PropertyDetail } from '@/api/schemas'
import {
  formatArea,
  formatCurrency,
  formatDate,
  formatDateTime,
} from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

type AvailablePropertyImage = PropertyDetail['images'][number] & {
  url: string
}

function formatBuildingPeriod(value: string | null) {
  if (!value) return '—'
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDate(value)
  return value
}

export function PropertyDetailPage() {
  const [searchParameters] = useSearchParams()
  const { propertyId = '' } = useParams()
  const propertyIdentifier = Number(propertyId)
  const hasValidIdentifier = Number.isInteger(propertyIdentifier)
    && propertyIdentifier > 0
  const rawCustomerIdentifier = Number(searchParameters.get('customerId'))
  const customerIdentifier = Number.isInteger(rawCustomerIdentifier)
    && rawCustomerIdentifier > 0
    ? rawCustomerIdentifier
    : null
  const catalogPath = `/properties${
    customerIdentifier ? `?customerId=${customerIdentifier}` : ''
  }`
  const propertyQuery = useQuery({
    ...propertyDetailQueryOptions(propertyIdentifier),
    enabled: hasValidIdentifier,
  })
  const sessionQuery = useQuery(sessionQueryOptions)
  const [selectedImage, setSelectedImage] = (
    useState<AvailablePropertyImage | null>(null)
  )
  const imageCloseButtonRef = useRef<HTMLButtonElement>(null)
  const imageTriggerRef = useRef<HTMLButtonElement | null>(null)
  useDocumentTitle(
    propertyQuery.data
      ? `${propertyQuery.data.realEstateComplex}, квартира ${propertyQuery.data.apartmentNumber}`
      : 'Карточка объекта',
  )

  const closeImage = () => {
    setSelectedImage(null)
    window.setTimeout(() => imageTriggerRef.current?.focus(), 0)
  }

  useEffect(() => {
    if (!selectedImage) return
    imageCloseButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeImage()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedImage])

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Объект не найден"
        description="Проверьте адрес или вернитесь к каталогу недвижимости."
        action={(
          <Link className="button button--secondary" to={catalogPath}>
            К каталогу
          </Link>
        )}
      />
    )
  }
  if (propertyQuery.isLoading) return <PageLoadingState />
  if (propertyQuery.isError || !propertyQuery.data) {
    return (
      <ErrorState
        title="Объект не найден или недоступен"
        onRetry={() => void propertyQuery.refetch()}
      />
    )
  }

  const property = propertyQuery.data
  const mortgagePath = (
    `/mortgage?propertyId=${property.id}`
    + `&propertyCost=${encodeURIComponent(property.propertyCost)}`
    + (customerIdentifier ? `&customerId=${customerIdentifier}` : '')
  )

  return (
    <div className="page-stack property-detail-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Карточка объекта</span>
          <h1>
            {property.realEstateComplex}, квартира {property.apartmentNumber}
          </h1>
          <p>
            {property.city}, {property.district}, корпус {property.building}
          </p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to={catalogPath}>
            К каталогу
          </Link>
          {sessionQuery.data?.capabilities.manageCatalogs ? (
            <>
              <a
                className="button button--secondary"
                href={property.legacyEditUrl}
              >
                Редактировать
              </a>
              <a
                className="button button--danger"
                href={property.legacyDeleteUrl}
              >
                Удалить
              </a>
            </>
          ) : null}
        </div>
      </header>

      <section
        className="property-highlight-card"
        aria-labelledby="property-price-title"
      >
        <div>
          <span className="eyebrow">Стоимость объекта</span>
          <h2 id="property-price-title">
            {formatCurrency(property.propertyCost)}
          </h2>
          <div className="property-highlight-card__tags">
            <span>{property.realEstateClass}</span>
            <span>{property.realEstateType}</span>
            <span>{property.layout}</span>
          </div>
        </div>
        <dl className="property-highlight-card__metrics">
          <div><dt>Площадь</dt><dd>{formatArea(property.area)}</dd></div>
          <div><dt>Этаж</dt><dd>{property.floor}</dd></div>
          <div><dt>Отделка</dt><dd>{property.decoration}</dd></div>
        </dl>
        <Link className="button button--primary" to={mortgagePath}>
          Рассчитать ипотеку
        </Link>
      </section>

      <div className="property-detail-sections">
        <section
          className="saved-property-card"
          aria-labelledby="property-information-title"
        >
          <div className="section-heading">
            <div>
              <span className="eyebrow">Квартира</span>
              <h2 id="property-information-title">Основная информация</h2>
            </div>
          </div>
          <dl className="property-detail-facts">
            <div><dt>Застройщик</dt><dd>{property.developer}</dd></div>
            <div><dt>Жилой комплекс</dt><dd>{property.realEstateComplex}</dd></div>
            <div><dt>Корпус</dt><dd>{property.building}</dd></div>
            <div><dt>Квартира</dt><dd>{property.apartmentNumber}</dd></div>
            <div>
              <dt>Планировка</dt>
              <dd>
                {property.layout}
                {property.layoutDescription
                  ? <small>{property.layoutDescription}</small>
                  : null}
              </dd>
            </div>
            <div>
              <dt>Отделка</dt>
              <dd>
                {property.decoration}
                {property.decorationDescription
                  ? <small>{property.decorationDescription}</small>
                  : null}
              </dd>
            </div>
            <div>
              <dt>Вид из окна</dt>
              <dd>
                {property.windowViews.length > 0
                  ? property.windowViews.join(', ')
                  : '—'}
              </dd>
            </div>
            <div><dt>Адрес корпуса</dt><dd>{property.buildingAddress || '—'}</dd></div>
          </dl>
        </section>

        <section
          className="saved-property-card"
          aria-labelledby="complex-information-title"
        >
          <div className="section-heading">
            <div>
              <span className="eyebrow">Жилой комплекс</span>
              <h2 id="complex-information-title">Локация и сроки</h2>
            </div>
          </div>
          <dl className="property-detail-facts">
            <div><dt>Регион</dt><dd>{property.region}</dd></div>
            <div><dt>Город</dt><dd>{property.city}</dd></div>
            <div><dt>Район</dt><dd>{property.district}</dd></div>
            <div>
              <dt>Ввод в эксплуатацию</dt>
              <dd>{formatBuildingPeriod(property.commissioning)}</dd>
            </div>
            <div>
              <dt>Выдача ключей</dt>
              <dd>{formatBuildingPeriod(property.keyHandover)}</dd>
            </div>
          </dl>
          {property.mapUrl || property.presentationUrl ? (
            <div className="property-resource-links">
              {property.mapUrl ? (
                <a href={property.mapUrl} target="_blank" rel="noreferrer">
                  Открыть на карте <span aria-hidden="true">↗</span>
                </a>
              ) : null}
              {property.presentationUrl ? (
                <a
                  href={property.presentationUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  Открыть презентацию <span aria-hidden="true">↗</span>
                </a>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>

      <section aria-labelledby="property-images-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Материалы</span>
            <h2 id="property-images-title">Изображения объекта</h2>
          </div>
        </div>
        <div className="property-image-grid">
          {property.images.map((image) => (
            <article className="property-image-card" key={image.kind}>
              <h3>{image.label}</h3>
              {image.url ? (
                <button
                  className="property-image-button"
                  type="button"
                  aria-label={`Увеличить: ${image.label}`}
                  onClick={(event) => {
                    imageTriggerRef.current = event.currentTarget
                    setSelectedImage({ ...image, url: image.url as string })
                  }}
                >
                  <img src={image.url} alt={image.label} loading="lazy" />
                </button>
              ) : (
                <div className="property-image-placeholder">
                  <span aria-hidden="true">⌂</span>
                  <p>Не загружено</p>
                </div>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="property-system-information" aria-label="Системная информация">
        <span>Создано: {formatDateTime(property.createdAt)}</span>
        <span>Обновлено: {formatDateTime(property.updatedAt)}</span>
      </section>

      <p className="legacy-fallback">
        Нужен прежний экран?{' '}
        <a className="text-link" href={property.legacyDetailUrl}>
          Открыть Django-версию
        </a>
      </p>

      {selectedImage ? (
        <div
          className="property-image-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="property-image-modal-title"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) closeImage()
          }}
        >
          <div className="property-image-modal__content">
            <div className="property-image-modal__header">
              <h2 id="property-image-modal-title">{selectedImage.label}</h2>
              <button
                className="icon-button"
                type="button"
                ref={imageCloseButtonRef}
                aria-label="Закрыть изображение"
                onClick={closeImage}
              >
                ×
              </button>
            </div>
            <img src={selectedImage.url} alt={selectedImage.label} />
            <a
              className="text-link"
              href={selectedImage.url}
              target="_blank"
              rel="noreferrer"
            >
              Открыть оригинал <span aria-hidden="true">↗</span>
            </a>
          </div>
        </div>
      ) : null}
    </div>
  )
}
