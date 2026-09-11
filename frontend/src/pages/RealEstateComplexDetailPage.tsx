import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  deleteRealEstateComplex,
  realEstateComplexDetailQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import { formatDate, formatDateTime, formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

function formatBuildingPeriod(value: string | null) {
  if (!value) return '—'
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDate(value)
  return value
}

export function RealEstateComplexDetailPage() {
  const { complexId = '' } = useParams()
  const complexIdentifier = Number(complexId)
  const hasValidIdentifier = Number.isInteger(complexIdentifier)
    && complexIdentifier > 0
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const complexQuery = useQuery({
    ...realEstateComplexDetailQueryOptions(complexIdentifier),
    enabled: hasValidIdentifier,
  })
  const sessionQuery = useQuery(sessionQueryOptions)
  const [isPhotoOpen, setIsPhotoOpen] = useState(false)
  const photoTriggerRef = useRef<HTMLButtonElement>(null)
  const photoCloseButtonRef = useRef<HTMLButtonElement>(null)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const deleteTriggerRef = useRef<HTMLButtonElement>(null)
  const deleteCancelButtonRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: () => deleteRealEstateComplex(complexIdentifier),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['real-estate-complexes'],
      })
      await queryClient.invalidateQueries({ queryKey: ['overview'] })
      queryClient.removeQueries({
        queryKey: ['real-estate-complex', complexIdentifier],
      })
      navigate('/complexes')
    },
  })
  useDocumentTitle(complexQuery.data?.name ?? 'Карточка жилого комплекса')

  const closePhoto = () => {
    setIsPhotoOpen(false)
    window.setTimeout(() => photoTriggerRef.current?.focus(), 0)
  }

  useEffect(() => {
    if (!isPhotoOpen) return
    photoCloseButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closePhoto()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isPhotoOpen])

  useEffect(() => {
    if (!isDeleteDialogOpen) return
    deleteCancelButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleteMutation.isPending) {
        setIsDeleteDialogOpen(false)
        window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [deleteMutation.isPending, isDeleteDialogOpen])

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Жилой комплекс не найден"
        description="Проверьте адрес или вернитесь к списку жилых комплексов."
        action={(
          <Link className="button button--secondary" to="/complexes">
            К списку
          </Link>
        )}
      />
    )
  }
  if (complexQuery.isLoading) return <PageLoadingState />
  if (complexQuery.isError || !complexQuery.data) {
    return (
      <ErrorState
        title="Жилой комплекс не найден или недоступен"
        onRetry={() => void complexQuery.refetch()}
      />
    )
  }

  const realEstateComplex = complexQuery.data
  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )

  return (
    <div className="page-stack complex-detail-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Карточка жилого комплекса</span>
          <h1>{realEstateComplex.name}</h1>
          <p>
            {realEstateComplex.city}, {realEstateComplex.district} ·{' '}
            {realEstateComplex.developer.label}
          </p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to="/complexes">
            К списку
          </Link>
          {canManageCatalogs ? (
            <>
              <Link
                className="button button--secondary"
                to={`/complexes/${realEstateComplex.id}/edit`}
              >
                Редактировать
              </Link>
              <button
                className="button button--danger"
                type="button"
                ref={deleteTriggerRef}
                onClick={() => {
                  deleteMutation.reset()
                  setIsDeleteDialogOpen(true)
                }}
              >
                Удалить
              </button>
            </>
          ) : null}
        </div>
      </header>

      <section className="complex-hero-card">
        <div className="complex-photo-card">
          {realEstateComplex.photoUrl ? (
            <button
              type="button"
              ref={photoTriggerRef}
              aria-label="Увеличить фото жилого комплекса"
              onClick={() => setIsPhotoOpen(true)}
            >
              <img
                src={realEstateComplex.photoUrl}
                alt={`Жилой комплекс ${realEstateComplex.name}`}
              />
            </button>
          ) : (
            <div className="complex-photo-placeholder">
              <span aria-hidden="true">⌂</span>
              <p>Фото жилого комплекса не загружено</p>
            </div>
          )}
        </div>
        <div className="complex-summary">
          <div className="property-highlight-card__tags">
            <span>{realEstateComplex.realEstateClass}</span>
            <span>{realEstateComplex.realEstateType}</span>
            <span>{realEstateComplex.isActive ? 'Активен' : 'Неактивен'}</span>
          </div>
          <dl className="property-detail-facts">
            <div><dt>Застройщик</dt><dd>{realEstateComplex.developer.label}</dd></div>
            <div><dt>Регион</dt><dd>{realEstateComplex.region}</dd></div>
            <div><dt>Город</dt><dd>{realEstateComplex.city}</dd></div>
            <div><dt>Район</dt><dd>{realEstateComplex.district}</dd></div>
            <div>
              <dt>Корпусов</dt>
              <dd>{formatInteger(realEstateComplex.buildings.length)}</dd>
            </div>
            <div>
              <dt>Станций метро</dt>
              <dd>{formatInteger(realEstateComplex.metroAvailability.length)}</dd>
            </div>
          </dl>
          {realEstateComplex.mapUrl || realEstateComplex.presentationUrl ? (
            <div className="property-resource-links">
              {realEstateComplex.mapUrl ? (
                <a href={realEstateComplex.mapUrl} target="_blank" rel="noreferrer">
                  Открыть на карте <span aria-hidden="true">↗</span>
                </a>
              ) : null}
              {realEstateComplex.presentationUrl ? (
                <a
                  href={realEstateComplex.presentationUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  Открыть презентацию <span aria-hidden="true">↗</span>
                </a>
              ) : null}
            </div>
          ) : null}
        </div>
      </section>

      <div className="complex-description-grid">
        <section className="saved-property-card">
          <div className="section-heading">
            <div><span className="eyebrow">О проекте</span><h2>Описание</h2></div>
          </div>
          <p className="complex-copy">
            {realEstateComplex.description || 'Описание не заполнено.'}
          </p>
        </section>
        <section className="saved-property-card">
          <div className="section-heading">
            <div><span className="eyebrow">Инвестиции</span><h2>Потенциал</h2></div>
          </div>
          <p className="complex-copy">
            {realEstateComplex.investmentPotential
              || 'Инвестиционный потенциал не заполнен.'}
          </p>
        </section>
      </div>

      <section className="saved-property-card" aria-labelledby="complex-buildings-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Состав проекта</span>
            <h2 id="complex-buildings-title">Корпуса</h2>
          </div>
        </div>
        {realEstateComplex.buildings.length ? (
          <div className="property-table-wrapper">
            <table className="property-table complex-related-table">
              <caption className="visually-hidden">Корпуса жилого комплекса</caption>
              <thead>
                <tr>
                  <th scope="col">Корпус</th>
                  <th scope="col">Адрес</th>
                  <th scope="col">Ввод</th>
                  <th scope="col">Ключи</th>
                  <th scope="col">Объектов</th>
                  <th scope="col">Статус</th>
                </tr>
              </thead>
              <tbody>
                {realEstateComplex.buildings.map((building) => (
                  <tr key={building.id}>
                    <td><strong>{building.number}</strong></td>
                    <td>{building.address || '—'}</td>
                    <td>{formatBuildingPeriod(building.commissioning)}</td>
                    <td>{formatBuildingPeriod(building.keyHandover)}</td>
                    <td>{formatInteger(building.propertyCount)}</td>
                    <td>{building.isActive ? 'Активен' : 'Неактивен'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="complex-copy">Корпуса не добавлены.</p>}
      </section>

      <section className="saved-property-card" aria-labelledby="complex-metro-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Транспорт</span>
            <h2 id="complex-metro-title">Доступность метро</h2>
          </div>
        </div>
        {realEstateComplex.metroAvailability.length ? (
          <div className="property-table-wrapper">
            <table className="property-table complex-related-table">
              <caption className="visually-hidden">Метро рядом с жилым комплексом</caption>
              <thead>
                <tr>
                  <th scope="col">Станция</th>
                  <th scope="col">Линия</th>
                  <th scope="col">Способ</th>
                  <th scope="col">Время</th>
                  <th scope="col">Статус</th>
                </tr>
              </thead>
              <tbody>
                {realEstateComplex.metroAvailability.map((availability) => (
                  <tr key={availability.id}>
                    <td>
                      <span
                        className="metro-dot"
                        style={{ backgroundColor: availability.lineColor }}
                        aria-hidden="true"
                      />
                      <strong>{availability.station}</strong>
                    </td>
                    <td>{availability.line}</td>
                    <td>{availability.transportAccessibilityType}</td>
                    <td>{availability.walkingTimeMinutes} мин.</td>
                    <td>{availability.isActive ? 'Активна' : 'Неактивна'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="complex-copy">Доступность метро не заполнена.</p>}
      </section>

      <section className="property-system-information" aria-label="Системная информация">
        <span>Создано: {formatDateTime(realEstateComplex.createdAt)}</span>
        <span>Обновлено: {formatDateTime(realEstateComplex.updatedAt)}</span>
      </section>
      <p className="legacy-fallback">
        Нужен прежний экран?{' '}
        <a className="text-link" href={realEstateComplex.legacyDetailUrl}>
          Открыть Django-версию
        </a>
      </p>

      {isPhotoOpen && realEstateComplex.photoUrl ? (
        <div
          className="property-image-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="complex-photo-modal-title"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) closePhoto()
          }}
        >
          <div className="property-image-modal__content">
            <div className="property-image-modal__header">
              <h2 id="complex-photo-modal-title">Фото {realEstateComplex.name}</h2>
              <button
                className="icon-button"
                type="button"
                ref={photoCloseButtonRef}
                aria-label="Закрыть изображение"
                onClick={closePhoto}
              >
                ×
              </button>
            </div>
            <img src={realEstateComplex.photoUrl} alt={realEstateComplex.name} />
          </div>
        </div>
      ) : null}

      {isDeleteDialogOpen ? (
        <div className="confirmation-dialog-backdrop" role="presentation">
          <section
            className="confirmation-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="complex-detail-delete-title"
            aria-describedby="complex-detail-delete-description"
          >
            <span className="eyebrow">Подтверждение</span>
            <h2 id="complex-detail-delete-title">Удалить жилой комплекс?</h2>
            <p id="complex-detail-delete-description">
              «{realEstateComplex.name}» будет удалён без возможности
              восстановления.
            </p>
            {deleteMutation.isError ? (
              <p className="form-error" role="alert">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'ЖК нельзя удалить, пока с его корпусами связаны объекты.'
                  : 'Не удалось удалить жилой комплекс. Повторите попытку.'}
              </p>
            ) : null}
            <div className="confirmation-dialog__actions">
              <button
                className="button button--secondary"
                type="button"
                ref={deleteCancelButtonRef}
                disabled={deleteMutation.isPending}
                onClick={() => setIsDeleteDialogOpen(false)}
              >
                Отмена
              </button>
              <button
                className="button button--danger"
                type="button"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
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
