import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { requestJson } from '@/api/client'
import { sessionQueryOptions } from '@/api/queries'
import { geographicPageSchema } from '@/features/locations/geography'
import '@/features/locations/locations.css'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'
import { LiveFilterInput } from '@/shared/ui/LiveFilterInput'
import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { NationalLocationImportPanel } from './NationalLocationImportPanel'

export function GeographyPage() {
  useDocumentTitle('Населённые пункты и территории России')
  const [parameters, setParameters] = useSearchParams()
  const session = useQuery(sessionQueryOptions)
  const queryParameters = new URLSearchParams(parameters)
  if (parameters.get('search')) queryParameters.set('q', parameters.get('search') ?? '')
  const queryString = queryParameters.toString()
  const query = useQuery({
    queryKey: ['geography', queryString],
    queryFn: ({ signal }) => requestJson(`/api/v1/locations/?${queryString}`, geographicPageSchema, { signal }),
  })
  const update = (name: string, value: string) => {
    const next = new URLSearchParams(parameters)
    if (value) next.set(name, value)
    else next.delete(name)
    if (name !== 'page') next.delete('page')
    setParameters(next)
  }
  return <div className="page-stack">
    <header className="page-header"><div><h1>Населённые пункты и территории России</h1>
      <p>Города, посёлки, сёла и деревни. Административные районы сохраняют отдельный уровень.</p></div></header>
    <nav className="section-navigation" aria-label="Справочники локаций">
      <Link to="/locations/regions">Регионы</Link>{' · '}
      <Link to="/locations/districts">Административные районы</Link>{' · '}
      <Link to="/locations/metro">Метро</Link>
    </nav>
    {session.data?.capabilities.syncExternalData ? <NationalLocationImportPanel /> : null}
    <section className="filter-panel geography-filters" aria-label="Фильтры территорий">
      <LiveFilterInput label="Поиск населённого пункта" id="geography-search" parameter="search" />
      <RemoteSelect filter dictionary="locations" filters={{ category: 'region' }} label="Регион"
        value={parameters.get('regionId') ?? ''} onChange={(value) => update('regionId', value)} />
      <label>Уровень<select value={parameters.get('category') ?? ''} onChange={(event) => update('category', event.target.value)}>
        <option value="">Все территории</option><option value="region">Регионы</option>
        <option value="district">Административные районы</option><option value="locality">Населённые пункты</option>
      </select></label>
    </section>
    {query.isLoading ? <PageLoadingState /> : query.isError ? <ErrorState onRetry={() => query.refetch()} /> : <>
      <p role="status">Найдено: {query.data?.totalCount ?? 0}</p>
      <TableScrollArea label="Населённые пункты и территории"><table><thead><tr><th>Название</th><th>Тип</th><th>Административная территория</th><th>Регион</th></tr></thead>
        <tbody>{query.data?.results.map((row) => <tr key={row.id}>
          <td>{row.name}{row.needsReview ? ' · требуется сверка' : ''}</td><td>{row.type}</td>
          <td>{row.parent ?? '—'}</td><td>{row.region ?? '—'}</td>
        </tr>)}</tbody></table></TableScrollArea>
      <div className="page-header__actions">
        <button type="button" disabled={Number(parameters.get('page') ?? 1) <= 1}
          onClick={() => update('page', String(Number(parameters.get('page') ?? 1) - 1))}>Назад</button>
        <button type="button" disabled={!query.data?.nextPage}
          onClick={() => update('page', String(query.data?.nextPage))}>Далее</button>
      </div>
    </>}
  </div>
}
