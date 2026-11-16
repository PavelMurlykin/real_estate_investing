import { screen, waitFor } from '@testing-library/react'
import { useLocation } from 'react-router-dom'
import { expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { LocationFilters } from './LocationFilters'

function Address() { return <output aria-label="Адрес">{useLocation().search}</output> }

it('converts legacy city URLs through canonical identity and keeps customer context', async () => {
  const location = {
    id: 900, label: 'г. Санкт-Петербург', name: 'Санкт-Петербург', type: 'Город', category: 'region',
    parentId: null, regionId: 900, parent: null, region: 'Санкт-Петербург', needsReview: false, isActive: true,
  }
  const fetchMock = vi.fn().mockImplementation(async (path: string) => Response.json(
    path.includes('legacyCityId=7')
      ? { results: [location], totalCount: 1, nextPage: null }
      : { results: [], selected: [], totalCount: 0, page: 1, nextPage: null },
  ))
  vi.stubGlobal('fetch', fetchMock)
  renderWithProviders(<><LocationFilters /><Address /></>, {
    initialRoute: '/?cityId=7&customerId=12&search=квартал&page=3',
  })
  await waitFor(() => {
    const parameters = new URLSearchParams(screen.getByLabelText('Адрес').textContent ?? '')
    expect(parameters.get('localityId')).toBe('900')
    expect(parameters.has('cityId')).toBe(false)
    expect(parameters.has('page')).toBe(false)
    expect(parameters.get('customerId')).toBe('12')
    expect(parameters.get('search')).toBe('квартал')
  })
})
