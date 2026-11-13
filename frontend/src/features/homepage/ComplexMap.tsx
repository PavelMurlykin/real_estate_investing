import { EmptyState, ErrorState, PageLoadingState, RetryButton } from '@/shared/ui/AsyncState'
import { useEffect, useRef, useState } from 'react'

import type { HomepageComplex } from '@/api/schemas'
import { coordinatesFromLink, escapeMapText, geocode, loadMapsSdk, safeMapUrl } from './mapSdk'
import type { MapInstance } from './mapSdk'

export default function ComplexMap({ complexes, city }: { complexes: Pick<HomepageComplex, 'id' | 'name' | 'mapUrl'>[]; city: string }) {
  const element = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'empty' | 'error'>('loading')
  const [retry, setRetry] = useState(0)
  const retryTask = useRef<{ promise: Promise<void>; resolve: () => void } | null>(null)
  const reload = () => {
    if (retryTask.current) return retryTask.current.promise
    let resolve: () => void = () => undefined
    const promise = new Promise<void>((complete) => { resolve = complete })
    retryTask.current = { promise, resolve }
    setRetry((current) => current + 1)
    return promise
  }
  useEffect(() => {
    const task = retryTask.current
    const complete = () => { task?.resolve(); if (retryTask.current === task) retryTask.current = null }
    let cancelled = false
    let map: MapInstance | undefined
    void Promise.resolve().then(async () => {
      if (cancelled) return
      setStatus('loading')
      const sdk = await loadMapsSdk()
      if (cancelled || !element.current) return
      map = new sdk.Map(element.current, {
        center: [59.939095, 30.315868], zoom: 11,
        controls: ['zoomControl', 'fullscreenControl'],
      }, { suppressMapOpenBlock: true })
      const currentMap = map
      let cursor = 0
      const addMarkers = async () => {
        while (!cancelled) {
          const complex = complexes[cursor++]
          if (!complex) return
          const coordinates = coordinatesFromLink(complex.mapUrl)
            ?? await geocode(sdk, complex.mapUrl)
            ?? await geocode(sdk, `${complex.name}, ${city}`)
          if (cancelled) return
          if (!coordinates) continue
          const label = escapeMapText(complex.name)
          const link = safeMapUrl(complex.mapUrl)
          currentMap.geoObjects.add(new sdk.Placemark(coordinates, {
            hintContent: label, iconCaption: label,
            balloonContent: `<strong>${label}</strong>${link ? `<br><a href="${escapeMapText(link)}" target="_blank" rel="noopener noreferrer">Открыть на Яндекс Картах</a>` : ''}`,
          }, { preset: 'islands#blueCircleDotIconWithCaption', iconCaptionMaxWidth: 220 }))
        }
      }
      await Promise.all([addMarkers(), addMarkers()])
      if (cancelled) return
      if (currentMap.geoObjects.getLength()) {
        await Promise.resolve(currentMap.setBounds(currentMap.geoObjects.getBounds(), { checkZoomRange: true, zoomMargin: 32 }))
      } else {
        const center = await geocode(sdk, city)
        if (!cancelled && center) await Promise.resolve(currentMap.setCenter(center, 11))
      }
      if (!cancelled) setStatus(currentMap.geoObjects.getLength() ? 'ready' : 'empty')
    }).catch(() => { if (!cancelled) setStatus('error') }).finally(complete)
    return () => { cancelled = true; map?.destroy(); complete() }
  }, [city, complexes, retry])
  return (
    <div className="complex-map-shell">
      <div ref={element} className="complex-map-canvas" role="region" aria-label={`Карта ЖК: ${city}`} hidden={status === 'error'} />
      {status === 'loading' ? <PageLoadingState compact title="Загружаем карту и координаты ЖК…" /> : null}
      {status === 'empty' ? <EmptyState compact title="Координаты ЖК не найдены. Прямые ссылки на карты доступны в карточках ниже."
        action={<RetryButton onRetry={reload} label="Повторить загрузку карты" />} /> : null}
      {status === 'error' ? <ErrorState title="Карта временно недоступна. Список ЖК и прямые ссылки доступны ниже."
        compact retryLabel="Повторить загрузку карты" onRetry={reload} /> : null}
    </div>
  )
}
