import { screen, waitFor } from '@testing-library/react'
import { useLocation } from 'react-router-dom'
import { expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'
import userEvent from '@testing-library/user-event'
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

it('converts a prefixed calculation city without changing the surrounding page filters', async () => {
  const location = {
    id: 900, label: 'г. Санкт-Петербург', name: 'Санкт-Петербург', type: 'Город', category: 'region',
    parentId: null, regionId: 900, parent: null, region: 'Санкт-Петербург', needsReview: false, isActive: true,
  }
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (path: string) => Response.json(
    path.includes('legacyCityId=7') ? { results: [location], totalCount: 1, nextPage: null }
      : { results: [], selected: [], totalCount: 0, page: 1, nextPage: null },
  )))
  renderWithProviders(<><LocationFilters prefix="calculation" /><Address /></>, {
    initialRoute: '/?calculationCity=7&calculationPage=3&calculationProgram=trench&localityId=111&customerId=12',
  })
  await waitFor(() => {
    const parameters = new URLSearchParams(screen.getByLabelText('Адрес').textContent ?? '')
    expect(parameters.get('calculationLocalityId')).toBe('900')
    expect(parameters.has('calculationCity')).toBe(false)
    expect(parameters.has('calculationPage')).toBe(false)
    expect(parameters.get('calculationProgram')).toBe('trench')
    expect(parameters.get('localityId')).toBe('111')
    expect(parameters.get('customerId')).toBe('12')
  })
})

it('clears only dependent calculation territories and keeps financial ranges', async () => {
  const user = userEvent.setup()
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (path: string) => {
    const parameters = new URL(path, 'http://localhost').searchParams
    return Response.json({ page: 1, nextPage: null, totalCount: 1,
      results: [{ id: 12, label: 'Новый регион' }],
      selected: parameters.getAll('selectedIds').map((value) => ({ id: Number(value), label: 'Прежний выбор' })),
    })
  }))
  renderWithProviders(<><LocationFilters prefix="calculation" /><Address /></>, {
    initialRoute: '/?calculationRegionLocationId=11&calculationDistrictLocationId=21&calculationLocalityId=31&calculationPage=3&calculationCostFrom=5000000&localityId=111',
  })
  await user.click(screen.getByRole('combobox', { name: 'Регион' }))
  await user.click(await screen.findByRole('option', { name: 'Новый регион' }))
  const parameters = new URLSearchParams(screen.getByLabelText('Адрес').textContent ?? '')
  expect(parameters.get('calculationRegionLocationId')).toBe('12')
  expect(parameters.has('calculationDistrictLocationId')).toBe(false)
  expect(parameters.has('calculationLocalityId')).toBe(false)
  expect(parameters.has('calculationPage')).toBe(false)
  expect(parameters.get('calculationCostFrom')).toBe('5000000')
  expect(parameters.get('localityId')).toBe('111')
})
