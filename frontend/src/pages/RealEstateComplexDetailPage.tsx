import { ComplexPhotos } from '@/features/realEstateComplex/ComplexPhotos'
import { TransportIcon } from '@/features/realEstateComplex/MetroAccess'
import { InteractiveTable } from '@/shared/ui/InteractiveTable'
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
        <ComplexPhotos key={realEstateComplex.id} complex={realEstateComplex} />
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
              <dt>Доступность метро</dt>
              <dd className="complex-metro-summary">
                {realEstateComplex.metroAvailability.filter((row) => row.isActive).map((row) => (
                  <span key={row.id}>
                    <TransportIcon mode={row.transportAccessibilityType} />
                    {row.station} ({row.line}) · {row.walkingTimeMinutes} мин.
                  </span>
                ))}
                {realEstateComplex.metroAvailability.length === 0 ? 'Не заполнена' : null}
              </dd>
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
            <InteractiveTable rows={realEstateComplex.buildings} getRowKey={(building) => building.id}
              caption={`Корпуса жилого комплекса`} className="property-table complex-related-table"
              columns={[
                { id: 'column0', label: "Корпус", value: (building) => building.number, render: (building) => <><strong>{building.number}</strong></> },
                { id: 'column1', label: "Адрес", value: (building) => building.address, render: (building) => <>{building.address || '—'}</> },
                { id: 'column2', label: "Ввод", value: (building) => building.commissioningDate ?? (building.commissioningYear ? `${building.commissioningYear}-${(building.commissioningQuarter ?? 1) * 3}-01` : null), searchValue: (building) => formatBuildingPeriod(building.commissioning), render: (building) => <>{formatBuildingPeriod(building.commissioning)}</> },
                { id: 'column3', label: "Ключи", value: (building) => building.keyHandoverDate ?? (building.keyHandoverYear ? `${building.keyHandoverYear}-${(building.keyHandoverQuarter ?? 1) * 3}-01` : null), searchValue: (building) => formatBuildingPeriod(building.keyHandover), render: (building) => <>{formatBuildingPeriod(building.keyHandover)}</> },
                { id: 'column4', label: "Объектов", value: (building) => building.propertyCount, render: (building) => <>{formatInteger(building.propertyCount)}</> },
              ]} />
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
            <InteractiveTable rows={realEstateComplex.metroAvailability} getRowKey={(availability) => availability.id}
              caption={`Метро рядом с жилым комплексом`} className="property-table complex-related-table"
              columns={[
                { id: 'column0', label: "Станция", value: (availability) => availability.station, render: (availability) => <><span
                        className="metro-dot"
                        style={{ backgroundColor: availability.lineColor }}
                        aria-hidden="true"
                      /><strong>{availability.station}</strong></> },
                { id: 'column1', label: "Линия", value: (availability) => availability.line, render: (availability) => <>{availability.line}</> },
                { id: 'column2', label: "Способ", value: (availability) => availability.transportAccessibilityType, render: (availability) => <TransportIcon mode={availability.transportAccessibilityType} /> },
                { id: 'column3', label: "Время", value: (availability) => availability.walkingTimeMinutes, render: (availability) => <>{availability.walkingTimeMinutes}мин.</> },
              ]} />
          </div>
        ) : <p className="complex-copy">Доступность метро не заполнена.</p>}
      </section>

      <section className="property-system-information" aria-label="Системная информация">
        <span>Создано: {formatDateTime(realEstateComplex.createdAt)}</span>
        <span>Обновлено: {formatDateTime(realEstateComplex.updatedAt)}</span>
      </section>

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
