import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiErrorMessage, requestJson } from '@/api/client'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'
import { Notice } from '@/shared/ui/Notice'
import { complexLocationsSchema } from './geography'
import type { ComplexLocations } from './geography'
import './locations.css'

function LocationsEditor({ data, complexId }: { data: ComplexLocations, complexId: number }) {
  const client = useQueryClient()
  const [locations, setLocations] = useState(data.locations.map((row) => ({ locationId: row.id, isPrimary: row.isPrimary })))
  const [buildings, setBuildings] = useState(data.buildings.map(({ id, locationId }) => ({ id, locationId })))
  const mutation = useMutation({
    mutationFn: () => requestJson(`/api/v1/complexes/${complexId}/locations/`, complexLocationsSchema, {
      method: 'PUT', body: JSON.stringify({ locations, buildings }),
    }),
    onSuccess: async (saved) => {
      client.setQueryData(['complex-locations', complexId], saved)
      await client.invalidateQueries({ queryKey: ['real-estate-complexes'] })
    },
  })
  const initialOptions = data.locations.map(({ id, label }) => ({ id, label }))
  return <form onSubmit={(event) => { event.preventDefault(); mutation.mutate() }} className="page-stack complex-locations-editor">
    {locations.map((row, index) => <div key={index} className="filter-panel">
      <RemoteSelect dictionary="locations" label={`Территория ${index + 1}`} value={String(row.locationId || '')}
        onChange={(value) => setLocations(locations.map((item, position) => position === index ? { ...item, locationId: Number(value) } : item))}
        initialOptions={initialOptions} truncated required />
      <label><input type="radio" name="primary-location" checked={row.isPrimary}
        onChange={() => setLocations(locations.map((item, position) => ({ ...item, isPrimary: position === index })))} /> Основная территория</label>
      {locations.length > 1 ? <button type="button" onClick={() => setLocations(locations.filter((_, position) => position !== index))}>Убрать территорию {index + 1}</button> : null}
    </div>)}
    <button type="button" onClick={() => setLocations([...locations, { locationId: 0, isPrimary: locations.length === 0 }])}>Добавить территорию</button>
    {data.buildings.map((building, index) => <label key={building.id}>Территория корпуса {building.number}
      <select value={String(buildings[index].locationId ?? '')} onChange={(event) => setBuildings(buildings.map((row) => row.id === building.id ? { ...row, locationId: event.target.value ? Number(event.target.value) : null } : row))}>
        <option value="">Наследовать основную территорию ЖК</option>
        {locations.filter((row) => row.locationId).map((row, position) => <option key={`${position}:${row.locationId}`} value={row.locationId}>
          {data.locations.find((item) => item.id === row.locationId)?.label ?? `Территория ${position + 1}`}
        </option>)}
      </select>
    </label>)}
    <button className="button button--primary" type="submit" disabled={mutation.isPending || !locations.length || locations.some((row) => !row.locationId)}>Сохранить территории ЖК</button>
    {mutation.isSuccess ? <Notice tone="success" role="status">Территории ЖК сохранены.</Notice> : null}
    {mutation.isError ? <Notice tone="error" role="alert">{apiErrorMessage(mutation.error) ?? 'Не удалось сохранить территории.'}</Notice> : null}
  </form>
}

export function ComplexLocationsPanel({ complexId, canManage }: { complexId: number, canManage: boolean }) {
  const query = useQuery({ queryKey: ['complex-locations', complexId],
    queryFn: ({ signal }) => requestJson(`/api/v1/complexes/${complexId}/locations/`, complexLocationsSchema, { signal }),
  })
  return <section className="saved-property-card detail-card" aria-labelledby="complex-locations-title">
    <h2 id="complex-locations-title">Территории ЖК</h2>
    {query.isLoading ? <p role="status">Загружаем территории…</p> : query.isError ? <Notice tone="error" role="alert">Не удалось загрузить территории. <button onClick={() => { void query.refetch() }}>Повторить</button></Notice> : query.data ? <>
      {query.data.locations.length ? <ul>{query.data.locations.map((row) => <li key={row.id}>{row.label}{row.isPrimary ? ' · основная' : ''}</li>)}</ul> : <p>Территория ещё не уточнена.</p>}
      {canManage ? <LocationsEditor key={query.dataUpdatedAt} data={query.data} complexId={complexId} /> : null}
    </> : null}
  </section>
}
