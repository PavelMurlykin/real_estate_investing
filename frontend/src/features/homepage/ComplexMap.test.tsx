import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import ComplexMap from './ComplexMap'
import type { MapsSdk } from './mapSdk'

const markerProperties: Record<string, string>[] = []
const destroyed = vi.fn()
let failCreation = false
class FakeMap {
  constructor() { if (failCreation) throw new Error('provider unavailable') }
  geoObjects = { add: vi.fn(), getLength: () => 1, getBounds: () => [[59.9, 30.3] as [number, number], [59.9, 30.3] as [number, number]] }
  setBounds = vi.fn()
  setCenter = vi.fn()
  destroy = destroyed
}
class FakePlacemark {
  constructor(_coordinates: [number, number], properties: Record<string, string>) { markerProperties.push(properties) }
}
const sdk: MapsSdk = { ready: (callback) => callback(), Map: FakeMap, Placemark: FakePlacemark, geocode: vi.fn() }
const markers = [{ id: 1, name: '<img src=x onerror=alert(1)>', mapUrl: 'https://yandex.ru/maps/?ll=30.3,59.9' }]

describe('ComplexMap', () => {
  it('uses explicit coordinates, escapes SDK markup and destroys the map on exit', async () => {
    window.ymaps = sdk
    const rendered = renderWithProviders(<ComplexMap city="Петербург" complexes={markers} />)
    await waitFor(() => expect(markerProperties).toHaveLength(1))
    expect(markerProperties[0].hintContent).toBe('&lt;img src=x onerror=alert(1)&gt;')
    expect(markerProperties[0].balloonContent).not.toContain('<img')
    expect(sdk.geocode).not.toHaveBeenCalled()
    rendered.unmount()
    expect(destroyed).toHaveBeenCalledTimes(1)
  })

  it('keeps a fallback and offers retry when the provider fails', async () => {
    const user = userEvent.setup()
    window.ymaps = sdk
    failCreation = true
    renderWithProviders(<ComplexMap city="Петербург" complexes={markers} />)
    expect(await screen.findByText(/Карта временно недоступна/)).toBeInTheDocument()
    failCreation = false
    await user.click(screen.getByRole('button', { name: 'Повторить загрузку карты' }))
    await waitFor(() => expect(screen.queryByText(/Карта временно недоступна/)).not.toBeInTheDocument())
  })
})
