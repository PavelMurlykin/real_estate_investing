import { useQuery } from '@tanstack/react-query'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { createTestQueryClient, renderWithProviders } from '@/test/render'
import { ComplexLocationsPanel } from './ComplexLocationsPanel'

const territory = (id: number, name: string, isPrimary: boolean, isHistorical: boolean) => ({
  id, name, label: name, type: 'Город', category: 'locality', parentId: null,
  regionId: null, parent: null, region: null, needsReview: false, isActive: true, isPrimary, isHistorical,
})

function SelectedPropertyLocation() {
  const query = useQuery({ queryKey: ['properties', 'selected'], staleTime: Infinity,
    queryFn: async () => (await fetch('/api/v1/properties/')).json() as Promise<{ city: string }>,
  })
  return <output aria-label="Территория выбранного объекта">{query.data?.city}</output>
}

it.each(['reactivate', 'make-primary'])('updates history and refreshes cached property geography: %s', async (action) => {
  const user = userEvent.setup()
  const data = { locations: [territory(10, 'Стрельна', true, false), territory(20, 'Пушкин', false, true)], buildings: [] }
  const fetchMock = vi.fn().mockImplementation(async (path: string, options?: RequestInit) => {
    if (path === '/api/v1/properties/') return Response.json({ city: 'Стрельна' })
    if (options?.method === 'PUT') {
      const payload = JSON.parse(options.body as string)
      return Response.json({ ...data, locations: data.locations.map((row, index) => ({
        ...row, isPrimary: payload.locations[index].isPrimary, isHistorical: payload.locations[index].isHistorical,
      })) })
    }
    if (path.includes('/catalog-options/')) return Response.json({
      results: data.locations, selected: data.locations, totalCount: 2, page: 1, nextPage: null,
    })
    return Response.json(data)
  })
  vi.stubGlobal('fetch', fetchMock)
  const client = createTestQueryClient()
  client.setQueryData(['properties', 'selected'], { city: 'Пушкин' })
  renderWithProviders(<><ComplexLocationsPanel complexId={1} canManage /><SelectedPropertyLocation /></>, { queryClient: client })
  const flags = await screen.findAllByRole('checkbox', { name: 'Историческая привязка' })
  expect(flags[0]).toBeDisabled()
  expect(flags[1]).toBeChecked()
  if (action === 'make-primary') {
    await user.click(screen.getAllByRole('radio', { name: 'Основная территория' })[1])
    expect(flags[0]).toBeChecked()
    expect(flags[1]).toBeDisabled()
  } else await user.click(flags[1])
  await user.click(screen.getByRole('button', { name: 'Сохранить территории ЖК' }))
  expect(await screen.findByText(action === 'make-primary' ? 'Пушкин · основная' : 'Пушкин · действующая')).toBeInTheDocument()
  expect(screen.getByLabelText('Территория выбранного объекта')).toHaveTextContent('Стрельна')
  const written = fetchMock.mock.calls.find(([, options]) => options?.method === 'PUT')
  expect(JSON.parse(written?.[1].body as string).locations[1].isHistorical).toBe(false)
})
