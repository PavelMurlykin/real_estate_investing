import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ApiError, requestJson, requestWithoutResponse } from '@/api/client'
import { sessionQueryOptions } from '@/api/queries'
import { locationCatalogEntrySchema, locationCatalogPageSchema, locationCatalogTitles, locationNavigation,
  type LocationCatalogEntry, type LocationCatalogKey } from '@/features/locations/catalog'
import { useLegacyLocation } from '@/features/locations/useLegacyLocation'
import { useTableParameters } from '@/shared/lib/useTableParameters'
import { useTableSearchParams } from '@/shared/lib/useTableSearchParams'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'
import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { ModalDialog } from '@/shared/ui/ModalDialog'
import { Notice } from '@/shared/ui/Notice'
import { Pagination } from '@/shared/ui/Pagination'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'
import { ResetFilters } from '@/shared/ui/ResetFilters'
import { SearchableSelect } from '@/shared/ui/SearchableSelect'
import { SectionNavigation } from '@/shared/ui/SectionNavigation'
import { SelectFilter } from '@/shared/ui/SelectFilter'
import { SortableHeader } from '@/shared/ui/SortableHeader'
import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { NationalLocationUpdateAction } from './NationalLocationUpdateAction'

function errorText(error: unknown) {
  if (error instanceof ApiError && error.details && typeof error.details === 'object') {
    return Object.values(error.details).flat().filter((value) => typeof value === 'string').join(' ')
      || error.message
  }
  return 'Не удалось сохранить изменения. Повторите попытку.'
}

function LocationEditor({ dictionaryKey, entry, types, onSaved }: {
  dictionaryKey: LocationCatalogKey; entry: LocationCatalogEntry | null
  types: { id: number; name: string }[]; onSaved: () => void
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(entry?.name ?? '')
  const [typeId, setTypeId] = useState(String(entry?.typeId ?? types[0]?.id ?? ''))
  const [regionId, setRegionId] = useState(String(entry?.regionId ?? ''))
  const [parentId, setParentId] = useState(String(entry?.parentId ?? ''))
  const [isActive, setIsActive] = useState(entry?.isActive ?? true)
  const save = useMutation({
    mutationFn: () => requestJson(`/api/v1/location-catalogs/${dictionaryKey}/${entry ? `${entry.id}/` : ''}`,
      locationCatalogEntrySchema, { method: entry ? 'PATCH' : 'POST', body: JSON.stringify({
        name, typeId: Number(typeId), parentId: parentId ? Number(parentId) : null, isActive,
      }) }),
    onSuccess: async () => { await queryClient.invalidateQueries(); if (!entry) setName(''); onSaved() },
  })
  const choices = types.map((type) => ({ value: String(type.id), label: type.name }))
  if (entry && !choices.some((choice) => choice.value === String(entry.typeId))) choices.push({ value: String(entry.typeId), label: entry.type })
  const submit = (event: FormEvent) => { event.preventDefault(); if (!save.isPending) save.mutate() }
  return <aside className="dictionary-form-card" aria-labelledby="location-form-title">
    <h2 id="location-form-title">{entry ? 'Редактирование записи' : 'Добавление записи'}</h2>
    <form onSubmit={submit}>
      <label className="form-field"><span>Название *</span><input required maxLength={255} value={name} onChange={(event) => setName(event.target.value)} /></label>
      <SearchableSelect label="Тип *" value={typeId} options={choices} onChange={setTypeId} />
      {dictionaryKey !== 'regions' ? <>
        <RemoteSelect dictionary="locations" label="Регион родителя" value={regionId} filters={{ category: 'region' }}
          onChange={(value) => { setRegionId(value); setParentId('') }} />
        <RemoteSelect dictionary="locations" label="Родительская территория" value={parentId}
          filters={{ regionId }} onChange={setParentId} required />
      </> : null}
      <label className="developer-active-field">
        <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} />
        <span>Запись активна</span>
      </label>
      {entry?.identifiers?.length ? <p className="field-hint">Повторный импорт может обновить официальное название и иерархию.</p> : null}
      {save.isError ? <Notice tone="error" className="form-error">{errorText(save.error)}</Notice> : null}
      <div className="dictionary-form-actions">
        <button className="button button--primary" disabled={save.isPending} type="submit">{save.isPending ? 'Сохраняем…' : 'Сохранить'}</button>
        {entry ? <button type="button" className="button button--secondary" disabled={save.isPending} onClick={onSaved}>Отмена</button> : null}
      </div>
    </form>
  </aside>
}

export function CanonicalLocationDictionaryPage({ dictionaryKey }: { dictionaryKey: LocationCatalogKey }) {
  const { dictionaryKey: routeKey, entryId = '' } = useParams()
  const navigate = useNavigate()
  const [parameters, setParameters] = useSearchParams()
  const [, updateParameters] = useTableSearchParams()
  const tableParameters = useTableParameters(parameters)
  tableParameters.set('status', 'active')
  const legacyCityCatalog = routeKey === 'cities' && !entryId
  if (legacyCityCatalog) {
    const oldRegionId = tableParameters.get('regionId')
    if (oldRegionId && !tableParameters.has('legacyRegionId')) {
      tableParameters.set('legacyRegionId', oldRegionId)
    }
    tableParameters.delete('regionId')
  }
  const oldCityId = dictionaryKey === 'districts' ? tableParameters.get('cityId') : null
  if (oldCityId) tableParameters.set('legacyCityId', oldCityId)
  const mappedRegion = useLegacyLocation('legacyRegionLookupId', tableParameters.get('legacyRegionId') ?? '').data
  const queryClient = useQueryClient()
  const session = useQuery(sessionQueryOptions)
  const title = locationCatalogTitles[dictionaryKey]
  useDocumentTitle(`Локации · ${title}`)
  const legacyId = entryId
  const editId = parameters.get('editLocationId') ?? legacyId
  const api = `/api/v1/location-catalogs/${dictionaryKey}/`
  const query = useQuery({ queryKey: ['location-catalogs', dictionaryKey, tableParameters.toString()],
    queryFn: ({ signal }) => requestJson(`${api}?${tableParameters}`, locationCatalogPageSchema, { signal }) })
  const detail = useQuery({ queryKey: ['location-catalog', dictionaryKey, editId, Boolean(legacyId)], enabled: Boolean(editId),
    queryFn: ({ signal }) => requestJson(`${api}${editId}/${legacyId ? '?legacy=1' : ''}`, locationCatalogEntrySchema, { signal }) })
  useEffect(() => {
    if (legacyId && detail.data?.category === 'region' && dictionaryKey !== 'regions') {
      navigate(`/locations/regions?editLocationId=${detail.data.id}`, { replace: true })
    }
  }, [legacyId, detail.data, dictionaryKey, navigate])
  const [deleting, setDeleting] = useState<LocationCatalogEntry | null>(null)
  const remove = useMutation({ mutationFn: (entry: LocationCatalogEntry) => requestWithoutResponse(`${api}${entry.id}/`, { method: 'DELETE' }),
    onSuccess: async () => { setDeleting(null); await queryClient.invalidateQueries() } })
  const closeEditor = () => { const next = new URLSearchParams(parameters); next.delete('editLocationId'); if (legacyId) navigate(`/locations/${dictionaryKey}?${next}`); else setParameters(next, { replace: true }) }
  const manage = session.data?.capabilities.manageCatalogs === true
  const region = mappedRegion ? String(mappedRegion.id) : legacyCityCatalog ? '' : parameters.get('regionId') ?? ''
  const hasTerritory = dictionaryKey !== 'regions'
  const tabs = <SectionNavigation label="Справочники локаций" items={locationNavigation} />
  return <div className="page-stack location-dictionary-page">
    <header className="page-header"><div><h1>{title}</h1>
      <p>{dictionaryKey === 'localities' ? 'Все города, посёлки, сёла и деревни России.' : dictionaryKey === 'districts' ? 'Административные районы; муниципальные образования ведутся отдельно.' : 'Регионы России.'}</p></div></header>
    {session.data?.capabilities.syncExternalData ? <NationalLocationUpdateAction>{tabs}</NationalLocationUpdateAction> : tabs}
    <section className="filter-panel location-filter-panel" aria-label={`Фильтры: ${title}`}>
      {dictionaryKey !== 'regions' ? <RemoteSelect filter dictionary="locations" label="Регион" value={region} filters={{ category: 'region' }}
        onChange={(value) => {
          const updateRegion = (next: URLSearchParams) => {
            if (value) next.set('regionId', value)
            else next.delete('regionId')
            for (const field of ['legacyRegionId', 'legacyCityId', 'cityId', 'ancestorId', 'page']) next.delete(field)
          }
          if (legacyCityCatalog) {
            const next = new URLSearchParams(parameters)
            updateRegion(next)
            navigate(`/locations/localities?${next}`)
          } else updateParameters(updateRegion)
        }} /> : null}
      {dictionaryKey === 'localities' ? <RemoteSelect filter dictionary="locations" label="Административный район" value={parameters.get('ancestorId') ?? ''}
        filters={{ category: 'district', regionId: region }} onChange={(value) => updateParameters((next) => { if (value) next.set('ancestorId', value); else next.delete('ancestorId'); next.delete('page') })} /> : null}
      <SelectFilter label="Тип" parameter="typeId" options={query.data?.types.map((type) => ({ value: String(type.id), label: type.name })) ?? []} />
      <div className="live-search-control" role="search">
        <LiveFilterInput label="Поиск" parameter="q" placeholder="Название или прежнее название" />
        <ResetFilters />
      </div>
    </section>
    {query.isLoading ? <PageLoadingState /> : query.isError || !query.data ? <ErrorState onRetry={() => query.refetch()} /> : <>
      <div className="results-heading" aria-live="polite"><p>Найдено: <strong>{query.data.totalCount}</strong></p></div>
      <div className={manage ? 'dictionary-workspace' : 'dictionary-workspace dictionary-workspace--public'}>
      <section aria-label={title}>
      {query.data.results.length ? <TableScrollArea className="table-card property-table-wrapper" label={title}>
        <table className="property-table location-catalog-table">
          <caption className="visually-hidden">{title}</caption>
          <colgroup>
            <col className="location-catalog-table__name" />
            <col />
            {hasTerritory ? <><col /><col /></> : null}
            {manage ? <col className="location-catalog-table__actions" /> : null}
          </colgroup>
          <thead><tr>
            <SortableHeader field="name">Название</SortableHeader>
            <SortableHeader field="type">Тип</SortableHeader>
            {hasTerritory ? <>
              <SortableHeader field="parent">Родительская территория</SortableHeader>
              <SortableHeader field="region">Регион</SortableHeader>
            </> : null}
            {manage ? <th scope="col"><span className="visually-hidden">Действия</span></th> : null}
          </tr></thead>
          <tbody>{query.data.results.map((row) => <tr key={row.id}>
            <td><strong>{row.name}</strong>{row.needsReview ? <p className="field-hint">Требуется сверка</p> : null}</td>
            <td>{row.type}</td>
            {hasTerritory ? <><td>{row.parent ?? '—'}</td><td>{row.region ?? '—'}</td></> : null}
            {manage ? <td><div className="row-actions">
              <Link className="row-action" aria-label={`Изменить: ${row.name}`} title={`Изменить: ${row.name}`}
                to={`/locations/${row.category === 'region' ? 'regions' : dictionaryKey}?editLocationId=${row.id}`}>✎</Link>
              <button className="row-action row-action--danger" type="button" aria-label={`Удалить: ${row.name}`} title={`Удалить: ${row.name}`}
                onClick={() => { remove.reset(); setDeleting(row) }}>×</button>
            </div></td> : null}
          </tr>)}</tbody>
        </table>
      </TableScrollArea>
      : <EmptyState title="Записей не найдено" description="Измените фильтры или добавьте первую запись." />}
      <Pagination label="Страницы локаций" page={query.data.page} totalPages={query.data.totalPages} onPageChange={(page) => updateParameters((next) => next.set('page', String(page)))} />
      </section>
      {manage ? (editId && detail.isLoading ? <PageLoadingState /> : editId && (detail.isError || !detail.data) ? <ErrorState onRetry={() => detail.refetch()} />
        : <LocationEditor key={editId ? detail.data?.id : `new-${dictionaryKey}`} dictionaryKey={editId && detail.data?.category === 'region' ? 'regions' : dictionaryKey}
          entry={editId ? detail.data ?? null : null} types={query.data.types} onSaved={closeEditor} />) : null}
      </div>
    </>}
    {deleting ? <ModalDialog label="Удалить локацию?" pending={remove.isPending} onClose={() => setDeleting(null)}>
      <h2>Удалить локацию?</h2><p>{deleting.name}. Связанные и импортированные записи защищены от удаления.</p>
      {remove.isError ? <p role="alert">{errorText(remove.error)}</p> : null}
      <div className="page-header__actions"><button type="button" className="button button--secondary" disabled={remove.isPending} onClick={() => setDeleting(null)}>Отмена</button>
        <button type="button" className="button button--danger" disabled={remove.isPending} onClick={() => remove.mutate(deleting)}>Удалить</button></div>
    </ModalDialog> : null}
    {legacyId && detail.data ? <Link className="text-link" to={`/locations/${dictionaryKey}?editLocationId=${detail.data.id}`}>Открыть актуальную ссылку записи</Link> : null}
  </div>
}
