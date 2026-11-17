import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { Session } from '@/api/schemas'
import type { LocationCatalogEntry, LocationCatalogKey } from '@/features/locations/catalog'
import { createTestQueryClient, renderWithProviders } from '@/test/render'
import { LocationDictionaryPage } from './LocationDictionaryPage'

const session: Session = { isAuthenticated: false, user: null,
  capabilities: { manageCatalogs: false, syncExternalData: false, viewPrivateRecords: false, viewAllPrivateRecords: false } }
const record: LocationCatalogEntry = {
  id: 1500, name: 'Пушкин', label: 'г. Пушкин · Пушкинский район · Санкт-Петербург',
  type: 'Город', typeId: 5, category: 'locality', parentId: 1475, parent: 'Пушкинский район',
  regionId: 64, region: 'Санкт-Петербург', needsReview: false, isActive: true,
  sourceStatus: 'verified', sourceVersion: '20261113', identifiers: [{ provider: 'fias', value: 'test-guid' }],
}

function setup(key: LocationCatalogKey, options: { manage?: boolean; route?: string; failure?: number } = {}) {
  let current = { ...record, ...(key === 'regions' ? {
    id: 64, name: 'Санкт-Петербург', typeId: 1, category: 'region', parentId: null, parent: null,
  } : {}) }
  const queryClient = createTestQueryClient()
  const currentSession = { ...session, capabilities: { ...session.capabilities, manageCatalogs: options.manage ?? false } }
  queryClient.setQueryData(['session'], currentSession)
  let writes = 0
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const path = String(input)
    if (path.includes('/auth/session/')) return Response.json(currentSession)
    if (init?.method === 'DELETE') return Response.json({ detail: 'Запись используется. Снимите флаг «Активно».' }, { status: 409 })
    if (init?.method === 'PATCH' || init?.method === 'POST') {
      writes += 1
      if (options.failure && writes === 1) return Response.json({ name: ['Исправьте название.'] }, { status: options.failure })
      current = { ...current, ...JSON.parse(init.body as string) }
      return Response.json(current, { status: init.method === 'POST' ? 201 : 200 })
    }
    if (path.includes('/catalog-options/')) return Response.json({
      results: [{ id: 64, label: 'г. Санкт-Петербург' }, { id: 1475, label: 'Пушкинский район' }],
      selected: [{ id: 64, label: 'г. Санкт-Петербург' }, { id: 1475, label: 'Пушкинский район' }],
      page: 1, nextPage: null, totalCount: 2,
    })
    if (/location-catalogs\/[^/]+\/\d+\//.test(path)) return Response.json(current)
    return Response.json({ results: [current], page: 1, totalPages: 2, totalCount: 21,
      types: [{ id: key === 'regions' ? 1 : 5, name: 'Город' }] })
  })
  vi.stubGlobal('fetch', fetchMock)
  renderWithProviders(<Routes>
    <Route path="/locations/:dictionaryKey" element={<LocationDictionaryPage />} />
    <Route path="/locations/:dictionaryKey/:entryId/edit" element={<LocationDictionaryPage />} />
  </Routes>, { queryClient, initialRoute: options.route ?? `/locations/${key}` })
  return { fetchMock, user: userEvent.setup() }
}

describe('canonical location dictionaries', () => {
  it('shows real localities publicly with administrative context and bounded pagination', async () => {
    const { user, fetchMock } = setup('localities')
    expect(await screen.findByRole('heading', { name: 'Населённые пункты' })).toBeInTheDocument()
    const table = await screen.findByRole('table', { name: 'Населённые пункты' })
    expect(within(table).getByText('Пушкин')).toBeInTheDocument()
    expect(within(table).getByText('Пушкинский район')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Сохранить' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Далее/ }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([path]) => String(path).includes('page=2'))).toBe(true))
    expect(fetchMock.mock.calls.some(([path]) => String(path).includes('/location-dictionaries/'))).toBe(false)
  })

  it.each(['regions', 'localities', 'districts'] as const)('opens %s on canonical IDs and preserves them on save', async (key) => {
    const identifier = key === 'regions' ? 64 : 1500
    const { user, fetchMock } = setup(key, { manage: true, route: `/locations/${key}?editLocationId=${identifier}` })
    const editor = within(await screen.findByRole('complementary', { name: 'Редактирование записи' }))
    const name = editor.getByLabelText('Название *')
    await user.clear(name)
    await user.type(name, 'Уточнённое название')
    await user.click(editor.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`/api/v1/location-catalogs/${key}/${identifier}/`, expect.objectContaining({ method: 'PATCH' })))
    expect(await screen.findByRole('complementary', { name: 'Добавление записи' })).toBeInTheDocument()
    expect(screen.getByLabelText('Название *')).toHaveValue('')
  })

  it('retains entered data after validation failure and permits retry', async () => {
    const { user, fetchMock } = setup('regions', { manage: true, failure: 400 })
    const name = await screen.findByLabelText('Название *')
    await user.type(name, 'Новый регион')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Исправьте название.')
    expect(name).toHaveValue('Новый регион')
    expect(screen.getByRole('button', { name: 'Сохранить' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(2))
  })

  it('keeps a protected imported locality and returns focus after the conflict dialog', async () => {
    const { user } = setup('localities', { manage: true })
    const trigger = await screen.findByRole('button', { name: 'Удалить: Пушкин' })
    await user.click(trigger)
    const dialog = screen.getByRole('alertdialog', { name: 'Удалить локацию?' })
    expect(within(dialog).getByRole('button', { name: 'Отмена' })).toHaveFocus()
    await user.click(within(dialog).getByRole('button', { name: 'Удалить' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Запись используется')
    await user.click(within(dialog).getByRole('button', { name: 'Отмена' }))
    expect(trigger).toHaveFocus()
  })

  it('translates old city edit URLs explicitly and saves the canonical identity', async () => {
    const { user, fetchMock } = setup('localities', { manage: true, route: '/locations/cities/7/edit' })
    const editor = within(await screen.findByRole('complementary', { name: 'Редактирование записи' }))
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/location-catalogs/localities/7/?legacy=1', expect.anything())
    await user.click(editor.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/location-catalogs/localities/1500/', expect.objectContaining({ method: 'PATCH' })))
  })

  it('opens the region editor when an old federal-city role maps to the same canonical subject', async () => {
    const { user, fetchMock } = setup('regions', { manage: true, route: '/locations/cities/7/edit' })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/location-catalogs/regions/64/', expect.anything()))
    const editor = within(await screen.findByRole('complementary', { name: 'Редактирование записи' }))
    expect(editor.queryByRole('combobox', { name: 'Родительская территория *' })).not.toBeInTheDocument()
    await user.click(editor.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/location-catalogs/regions/64/', expect.objectContaining({ method: 'PATCH' })))
  })
})
