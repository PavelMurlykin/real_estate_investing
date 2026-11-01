export type Coordinates = [number, number]
type MapBounds = Coordinates[]

export type MapInstance = {
  geoObjects: { add: (marker: unknown) => void; getLength: () => number; getBounds: () => MapBounds }
  setBounds: (bounds: MapBounds, options: { checkZoomRange: boolean; zoomMargin: number }) => unknown
  setCenter: (coordinates: Coordinates, zoom: number) => unknown
  destroy: () => void
}

export type MapsSdk = {
  ready: (callback: () => void) => void
  Map: new (element: HTMLElement, state: { center: Coordinates; zoom: number; controls: string[] }, options: { suppressMapOpenBlock: boolean }) => MapInstance
  Placemark: new (coordinates: Coordinates, properties: Record<string, string>, options: Record<string, string | number>) => unknown
  geocode: (query: string, options: { results: number }) => Promise<{ geoObjects: { get: (index: number) => { geometry: { getCoordinates: () => Coordinates } } | undefined } }>
}

declare global { interface Window { ymaps?: MapsSdk } }

let sdkPromise: Promise<MapsSdk> | null = null
const coordinateCache = new Map<string, Promise<Coordinates | null>>()

export function loadMapsSdk(): Promise<MapsSdk> {
  if (sdkPromise) return sdkPromise
  sdkPromise = new Promise<MapsSdk>((resolve, reject) => {
    const script = document.createElement('script')
    const timeout = window.setTimeout(() => {
      script?.remove()
      reject(new Error('Map load timed out'))
    }, 12_000)
    const fail = () => { window.clearTimeout(timeout); script?.remove(); reject(new Error('Map service unavailable')) }
    const ready = () => {
      const sdk = window.ymaps
      if (!sdk) { fail(); return }
      try {
        sdk.ready(() => { window.clearTimeout(timeout); resolve(sdk) })
      } catch { fail() }
    }
    if (window.ymaps) { ready(); return }
    script.src = 'https://api-maps.yandex.ru/2.1/?lang=ru_RU'
    script.async = true
    script.addEventListener('load', ready, { once: true })
    script.addEventListener('error', fail, { once: true })
    document.head.append(script)
  }).catch((error: unknown) => { sdkPromise = null; throw error })
  return sdkPromise
}

export function coordinatesFromLink(link: string | null): Coordinates | null {
  if (!link) return null
  try {
    const url = new URL(link)
    const match = (url.searchParams.get('ll') || url.searchParams.get('pt'))?.match(/(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/)
    if (!match) return null
    const longitude = Number(match[1])
    const latitude = Number(match[2])
    return Math.abs(longitude) <= 180 && Math.abs(latitude) <= 90 ? [latitude, longitude] : null
  } catch { return null }
}

export async function geocode(sdk: Pick<MapsSdk, 'geocode'>, query: string | null): Promise<Coordinates | null> {
  if (!query) return null
  const cached = coordinateCache.get(query)
  if (cached) return cached
  const result = Promise.resolve().then(async () => {
    try {
      const response = await sdk.geocode(query, { results: 1 })
      return response.geoObjects.get(0)?.geometry.getCoordinates() ?? null
    } catch { return null }
  })
  coordinateCache.set(query, result)
  if (coordinateCache.size > 500) coordinateCache.delete(coordinateCache.keys().next().value ?? '')
  if (await result === null) coordinateCache.delete(query)
  return result
}

export function escapeMapText(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[character] ?? character)
}

export function safeMapUrl(value: string | null): string | null {
  if (!value) return null
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) ? url.href : null
  } catch { return null }
}
