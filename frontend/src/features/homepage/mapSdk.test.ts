import { describe, expect, it, vi } from 'vitest'

import { coordinatesFromLink, escapeMapText, geocode, loadMapsSdk, safeMapUrl } from './mapSdk'
import type { MapsSdk } from './mapSdk'

describe('map data and loader', () => {
  it('uses longitude/latitude link coordinates and rejects invalid ranges and protocols', () => {
    expect(coordinatesFromLink('https://yandex.ru/maps/?ll=30.3%2C59.9')).toEqual([59.9, 30.3])
    expect(coordinatesFromLink('https://yandex.ru/maps/?pt=30.3,59.9,pm2rdm')).toEqual([59.9, 30.3])
    expect(coordinatesFromLink('https://yandex.ru/maps/?ll=200,95')).toBeNull()
    expect(coordinatesFromLink('invalid')).toBeNull()
    expect(safeMapUrl('javascript:alert(1)')).toBeNull()
    expect(escapeMapText('<img src="x">&')).toBe('&lt;img src=&quot;x&quot;&gt;&amp;')
  })

  it('caches successful geocoding and retries temporary failures', async () => {
    const geocoder = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({
      geoObjects: { get: () => ({ geometry: { getCoordinates: () => [59.9, 30.3] } }) },
    })
    const sdk = { geocode: geocoder }
    expect(await geocode(sdk, 'Тестовый город кеша')).toBeNull()
    expect(await geocode(sdk, 'Тестовый город кеша')).toEqual([59.9, 30.3])
    expect(await geocode(sdk, 'Тестовый город кеша')).toEqual([59.9, 30.3])
    expect(geocoder).toHaveBeenCalledTimes(2)
  })

  it('recovers from a failed SDK download instead of retaining a rejected promise', async () => {
    delete window.ymaps
    const loading = loadMapsSdk()
    const script = document.querySelector('script[src^="https://api-maps.yandex.ru/"]')
    expect(script).toBeInTheDocument()
    script?.dispatchEvent(new Event('error'))
    await expect(loading).rejects.toThrow('Map service unavailable')
    expect(script).not.toBeInTheDocument()
    const sdk = { ready: (callback: () => void) => callback() } as MapsSdk
    window.ymaps = sdk
    expect(await loadMapsSdk()).toBe(sdk)
    delete window.ymaps
  })
})
