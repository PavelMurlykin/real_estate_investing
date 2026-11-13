import { useInfiniteQuery } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { fetchHomepageComplexes } from '@/api/queries'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'

const ComplexMap = lazy(() => import('./ComplexMap'))

export function HomepageComplexes() {
  const [parameters, setParameters] = useSearchParams()
  const city = parameters.get('city') ?? ''
  const view = parameters.get('view') === 'map' ? 'map' : 'list'
  const complexesQuery = useInfiniteQuery({
    queryKey: ['homepage-complexes', city], initialPageParam: 1,
    queryFn: ({ pageParam, signal }) => fetchHomepageComplexes(city, pageParam, signal),
    getNextPageParam: (last) => last.page < last.totalPages ? last.page + 1 : undefined,
    placeholderData: (previous) => previous,
    staleTime: 60_000,
  })
  const data = complexesQuery.data?.pages[0]
  const selectedCity = data?.selectedCity
  const complexes = [...new Map(complexesQuery.data?.pages.flatMap((page) => page.results).map((item) => [item.id, item]) ?? []).values()]
  const update = (name: string, value: string) => {
    const next = new URLSearchParams(parameters)
    if (value) next.set(name, value)
    else next.delete(name)
    next.delete('page')
    setParameters(next)
  }
  return (
    <section className="homepage-complexes" aria-labelledby="homepage-complexes-title">
      <div className="section-heading">
        <div><span className="eyebrow">Подбор недвижимости</span><h2 id="homepage-complexes-title">Жилые комплексы по городам</h2></div>
      </div>
      <div className="filter-panel">
        <RemoteSelect filter dictionary="cities" label="Город на главной"
          value={complexesQuery.isPlaceholderData ? city : selectedCity ? String(selectedCity.id) : ''}
          initialOptions={selectedCity ? [{ id: selectedCity.id, label: selectedCity.name }] : []}
          truncated filters={{ activeOnly: 'true' }} onChange={(value) => update('city', value)} />
        <div className="homepage-view-switcher" role="group" aria-label="Режим отображения ЖК">
          <button type="button" className={`button button--${view === 'list' ? 'primary' : 'secondary'}`} aria-pressed={view === 'list'} onClick={() => update('view', 'list')}>Списком</button>
          <button type="button" className={`button button--${view === 'map' ? 'primary' : 'secondary'}`} aria-pressed={view === 'map'} onClick={() => update('view', 'map')}>На карте</button>
        </div>
      </div>
      {complexesQuery.isLoading || complexesQuery.isPlaceholderData ? <PageLoadingState compact title="Загружаем ЖК выбранного города…" /> : null}
      {complexesQuery.isError ? <ErrorState title="Не удалось загрузить жилые комплексы"
        onRetry={() => data ? complexesQuery.fetchNextPage() : complexesQuery.refetch()} /> : null}
      {data && !complexesQuery.isPlaceholderData ? <>
        <div className="results-heading" aria-live="polite"><p>ЖК в городе {selectedCity?.name ?? '—'}: <strong>{data.totalCount}</strong>. Показано: {complexes.length}.</p></div>
        {view === 'map' && complexes.length && selectedCity ? (
          <Suspense fallback={<PageLoadingState compact title="Загружаем карту…" />}>
            <ComplexMap complexes={complexes} city={selectedCity.name} />
          </Suspense>
        ) : null}
        {complexes.length ? <div className="homepage-complex-grid">
          {complexes.map((complex) => (
            <article key={complex.id} className="homepage-complex-card">
              {complex.photoUrl ? <img className="homepage-complex-card__photo" src={complex.photoUrl} alt={complex.name} loading="lazy" /> : <div className="homepage-complex-card__placeholder" aria-hidden="true">ЖК</div>}
              <div className="homepage-complex-card__body">
                <h3>{complex.name}</h3>
                <dl className="saved-property-grid">
                  <div><dt>Застройщик</dt><dd>{complex.developer.label}</dd></div>
                  <div><dt>Район</dt><dd>{complex.district}</dd></div>
                  <div><dt>Класс</dt><dd>{complex.realEstateClass}</dd></div>
                  <div><dt>Тип недвижимости</dt><dd>{complex.realEstateType}</dd></div>
                </dl>
                {complex.description ? <p className="complex-copy">{complex.description}</p> : null}
                <div className="page-header__actions">
                  <Link className="button button--secondary" to={`/complexes/${complex.id}`}>Подробнее о ЖК</Link>
                  <Link className="button button--primary" to={`/properties?realEstateComplex=${complex.id}`}>Объекты ЖК</Link>
                  {complex.mapUrl ? <a className="button button--secondary" href={complex.mapUrl} target="_blank" rel="noreferrer">Карта ЖК</a> : null}
                  {complex.presentationUrl ? <a className="text-link" href={complex.presentationUrl} target="_blank" rel="noreferrer">Презентация</a> : null}
                </div>
              </div>
            </article>
          ))}
        </div> : <EmptyState title="В выбранном городе пока нет ЖК" description="Выберите другой активный город или вернитесь позже." />}
        {complexesQuery.hasNextPage ? <button type="button" className="button button--secondary" disabled={complexesQuery.isFetching} onClick={() => void complexesQuery.fetchNextPage()}>{complexesQuery.isFetchingNextPage ? 'Загружаем…' : 'Показать ещё ЖК'}</button> : null}
      </> : null}
    </section>
  )
}
