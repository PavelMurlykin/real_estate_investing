import { chooseOption } from '@/test/chooseOption'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type {
  PropertyDetail,
  PropertyFormOptions,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { PropertyFormPage } from './PropertyFormPage'

const managerSession: Session = {
  isAuthenticated: true,
  user: {
    id: 1,
    displayName: 'Модератор',
    email: 'moderator@example.com',
    agencyName: '',
  },
  capabilities: {
    manageCatalogs: true,
    syncExternalData: false,
    viewPrivateRecords: true,
    viewAllPrivateRecords: false,
  },
}

const formOptions: PropertyFormOptions = {
  regions: [],
  cities: [],
  districts: [],
  developers: [{ id: 4, label: 'Северный девелопер' }],
  realEstateComplexes: [{ id: 5, name: 'Белые ночи' }],
  buildings: [{ id: 6, number: '1' }],
  layouts: [{ id: 7, name: 'Евродвушка' }],
  decorations: [{ id: 8, name: 'Чистовая' }],
  windowViews: [{ id: 9, name: 'Парк' }],
  truncated: {
    regions: false,
    cities: false,
    districts: false,
    developers: false,
    realEstateComplexes: false,
    buildings: false,
    layouts: false,
    decorations: false,
    windowViews: false,
  },
}

const propertyDetail: PropertyDetail = {
  id: 12,
  apartmentNumber: '101',
  regionId: 1,
  cityId: 2,
  districtId: 3,
  regionLocationId: 101,
  districtLocationId: 103,
  localityId: 102,
  developerId: 4,
  realEstateComplexId: 5,
  buildingId: 6,
  layoutId: 7,
  decorationId: 8,
  windowViewIds: [9],
  developer: 'Северный девелопер',
  realEstateComplex: 'Белые ночи',
  realEstateClass: 'Бизнес',
  realEstateType: 'Квартира',
  district: 'Петроградский',
  city: 'Санкт-Петербург',
  region: 'Ленинградская область',
  building: '1',
  buildingAddress: null,
  commissioning: null,
  keyHandover: null,
  layout: 'Евродвушка',
  layoutDescription: null,
  decoration: 'Чистовая',
  decorationDescription: null,
  windowViews: ['Парк'],
  area: '42.50',
  floor: 10,
  propertyCost: '12500000.00',
  mapUrl: null,
  presentationUrl: null,
  images: [
    {
      kind: 'layout',
      label: 'Планировка',
      url: '/media/property/layouts/layout.webp',
    },
    { kind: 'floorPlan', label: 'План этажа', url: null },
    { kind: 'windowView', label: 'Вид из окна', url: null },
  ],
  createdAt: '2026-09-01T10:00:00+03:00',
  updatedAt: '2026-09-09T12:30:00+03:00',
  legacyDetailUrl: '/property/12/',
  legacyEditUrl: '/property/12/update/',
  legacyDeleteUrl: '/property/12/delete/',
}

function mockLocationCatalogs() {
  const original = globalThis.fetch
  vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
    const url = new URL(String(path), 'http://localhost')
    if (url.pathname === '/api/v1/properties/options/') return Response.json(formOptions)
    const dictionary = url.pathname.match(/\/catalog-options\/([^/]+)\//)?.[1]
    const geography = { regionLocationId: 101, districtLocationId: 103, localityId: 102, developerId: 4, realEstateComplexId: 5 }
    const location = url.searchParams.get('category') === 'region'
      ? { id: 101, label: 'Ленинградская область' }
      : url.searchParams.get('category') === 'district'
        ? { id: 103, label: 'Петроградский' } : { id: 102, label: 'Санкт-Петербург' }
    const choice = dictionary === 'locations' ? location
      : dictionary === 'complexes' ? { id: 5, label: 'Белые ночи', ...geography }
        : dictionary === 'buildings' ? { id: 6, label: '1', ...geography } : null
    if (choice) return Response.json({ results: [choice], selected: [choice], totalCount: 1, page: 1, nextPage: null })
    return original(path, options)
  }))
}

function createManagerQueryClient() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['session'], managerSession)
  queryClient.setQueryData(['property-form-options', 'canonical'], formOptions)
  return queryClient
}

function renderCreateForm() {
  mockLocationCatalogs()
  const queryClient = createManagerQueryClient()
  return renderWithProviders(
    <Routes>
      <Route path="/properties/new" element={<PropertyFormPage />} />
      <Route path="/properties/:propertyId" element={<h1>Объект сохранён</h1>} />
    </Routes>,
    { initialRoute: '/properties/new', queryClient },
  )
}

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await chooseOption(user, 'Регион', 'Ленинградская область')
  await chooseOption(user, 'Административный район', 'Петроградский')
  await chooseOption(user, 'Населённый пункт', 'Санкт-Петербург')
  await chooseOption(user, 'Застройщик *', 'Северный девелопер')
  await chooseOption(user, 'Жилой комплекс *', 'Белые ночи')
  await chooseOption(user, 'Корпус *', '1')
  await user.type(screen.getByLabelText('Номер квартиры *'), '303')
  await user.type(screen.getByLabelText('Площадь, м² *'), '61.25')
  await user.type(screen.getByLabelText('Этаж *'), '12')
  await user.type(screen.getByLabelText('Стоимость, ₽ *'), '19000000')
  await chooseOption(user, 'Планировка *', 'Евродвушка')
  await chooseOption(user, 'Отделка *', 'Чистовая')
  await chooseOption(user, 'Вид из окна', 'Парк')
}

describe('PropertyFormPage', () => {
  it('allows locality selection without parents and fills geography only after choosing a building', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn())
    renderCreateForm()
    expect(screen.getByRole('combobox', { name: 'Населённый пункт' })).toBeEnabled()
    await chooseOption(user, 'Застройщик *', 'Северный девелопер')
    await chooseOption(user, 'Жилой комплекс *', 'Белые ночи')
    expect(screen.getByRole('combobox', { name: 'Населённый пункт' })).toHaveValue('')
    await chooseOption(user, 'Корпус *', '1')
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Населённый пункт' })).toHaveValue('Санкт-Петербург'))
    expect(screen.getByRole('combobox', { name: 'Административный район' })).toHaveValue('Петроградский')
    expect(screen.getByRole('combobox', { name: 'Регион' })).toHaveValue('Ленинградская область')
  })

  it.each([
    ['Регион', ['Административный район', 'Населённый пункт', 'Жилой комплекс *', 'Корпус *']],
    ['Административный район', ['Населённый пункт', 'Жилой комплекс *', 'Корпус *']],
    ['Населённый пункт', ['Жилой комплекс *', 'Корпус *']],
    ['Застройщик *', ['Жилой комплекс *', 'Корпус *']],
    ['Жилой комплекс *', ['Корпус *']],
  ])('clears dependent choices after clearing %s and preserves them on reselect', async (parent, children) => {
    const user = userEvent.setup()
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => Response.json(formOptions))
    vi.stubGlobal('fetch', fetchMock)
    renderCreateForm()
    await fillRequiredFields(user)
    const input = screen.getByRole('combobox', { name: parent })
    const original = (input as HTMLInputElement).value
    await chooseOption(user, parent, original)
    expect(screen.getByRole('combobox', { name: 'Корпус *' })).toHaveValue('1')
    await chooseOption(user, parent, 'Не выбрано')
    for (const child of children) {
      expect(screen.getByRole('combobox', { name: child })).toHaveValue('')
      if (child !== 'Корпус *' && !(child === 'Жилой комплекс *' && parent === 'Застройщик *')) {
        expect(screen.getByRole('combobox', { name: child })).toBeEnabled()
      } else {
        expect(screen.getByRole('combobox', { name: child })).toBeDisabled()
      }
    }
    expect(screen.getByRole('combobox', { name: 'Планировка *' })).toHaveValue('Евродвушка')
    expect(screen.getByRole('combobox', { name: 'Отделка *' })).toHaveValue('Чистовая')
    expect(fetchMock.mock.calls.every(([, options]) => !options?.method || options.method === 'GET')).toBe(true)
  })

  it('finds a layout outside the initial dictionary and submits its identifier', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockImplementation(async (path: string) => {
      if (path.includes('/catalog-options/layouts/')) {
        return new Response(JSON.stringify({
          results: [{ id: 205, label: 'Редкая планировка' }],
          selected: [], totalCount: 1, page: 1, nextPage: null,
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({ ...propertyDetail, id: 99 }), {
        status: 201, headers: { 'Content-Type': 'application/json' },
      })
    })
    vi.stubGlobal('fetch', fetchMock)
    const { queryClient } = renderCreateForm()
    await fillRequiredFields(user)
    queryClient.setQueryData(['property-form-options', 'canonical'], { ...formOptions, truncated: { ...formOptions.truncated, layouts: true } })
    await user.click(screen.getByRole('combobox', { name: 'Планировка *' }))
    await user.type(screen.getByRole('combobox', { name: 'Планировка *' }), 'Редкая')
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Планировка *' })).not.toHaveAttribute('aria-busy', 'true'))
    await user.click(await screen.findByRole('option', { name: 'Редкая планировка' }))
    await user.click(screen.getByRole('button', { name: 'Создать объект' }))
    expect(await screen.findByRole('heading', { name: 'Объект сохранён' })).toBeInTheDocument()
    const request = fetchMock.mock.calls.find(([path]) => path === '/api/v1/properties/')
    expect((request?.[1].body as FormData).get('layoutId')).toBe('205')
  })

  it('does not expose the form to users without catalog permissions', () => {
    renderWithProviders(
      <Routes>
        <Route path="/properties/new" element={<PropertyFormPage />} />
      </Routes>,
      { initialRoute: '/properties/new' },
    )

    expect(
      screen.getByRole('heading', { name: 'Недостаточно прав' }),
    ).toBeInTheDocument()
  })

  it('creates a property through multipart API and opens its React card', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...propertyDetail, id: 99 }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderCreateForm()

    await fillRequiredFields(user)
    await user.click(screen.getByRole('button', { name: 'Создать объект' }))

    expect(
      await screen.findByRole('heading', { name: 'Объект сохранён' }),
    ).toBeInTheDocument()
    const writes = fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')
    expect(writes).toHaveLength(1)
    const [requestPath, requestOptions] = writes[0] as [
      string,
      RequestInit,
    ]
    expect(requestPath).toBe('/api/v1/properties/')
    expect(requestOptions.method).toBe('POST')
    expect(requestOptions.body).toBeInstanceOf(FormData)
    const formData = requestOptions.body as FormData
    expect(formData.get('apartmentNumber')).toBe('303')
    expect(formData.get('buildingId')).toBe('6')
    expect(formData.getAll('windowViewIds')).toEqual(['9'])
    expect(formData.get('replaceWindowViews')).toBe('true')
  })

  it('shows authoritative property API errors beside a field', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            apartmentNumber: ['Объект с таким номером уже существует.'],
          }),
          {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      ),
    )
    renderCreateForm()

    await fillRequiredFields(user)
    await user.click(screen.getByRole('button', { name: 'Создать объект' }))

    expect(
      await screen.findByText('Объект с таким номером уже существует.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /Номер квартиры/ })).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('prefills the edit form and submits an explicit image clear flag', async () => {
    const user = userEvent.setup()
    const queryClient = createManagerQueryClient()
    queryClient.setQueryData(['property', 12], propertyDetail)
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ...propertyDetail,
          images: propertyDetail.images.map((image) => (
            image.kind === 'layout' ? { ...image, url: null } : image
          )),
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    mockLocationCatalogs()
    renderWithProviders(
      <Routes>
        <Route path="/properties/:propertyId/edit" element={<PropertyFormPage />} />
        <Route path="/properties/:propertyId" element={<h1>Объект сохранён</h1>} />
      </Routes>,
      { initialRoute: '/properties/12/edit', queryClient },
    )

    expect(await screen.findByLabelText('Номер квартиры *')).toHaveValue('101')
    expect(screen.getByRole('button', { name: 'Убрать: Парк' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Django-форма' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Удалить текущее' }))
    await user.click(
      screen.getByRole('button', { name: 'Сохранить изменения' }),
    )

    await screen.findByRole('heading', { name: 'Объект сохранён' })
    const requestOptions = fetchMock.mock.calls.find(([, options]) => options?.method === 'PATCH')?.[1] as RequestInit
    const formData = requestOptions.body as FormData
    expect(requestOptions.method).toBe('PATCH')
    expect(formData.get('clearLayoutImage')).toBe('true')
  })

  it('preserves an existing building when its canonical locality is still unknown', async () => {
    const user = userEvent.setup()
    const unknown = { ...propertyDetail, regionLocationId: null, districtLocationId: null, localityId: null }
    const queryClient = createManagerQueryClient()
    queryClient.setQueryData(['property', 12], unknown)
    const writes = vi.fn().mockResolvedValue(Response.json(unknown))
    vi.stubGlobal('fetch', writes)
    mockLocationCatalogs()
    renderWithProviders(<Routes>
      <Route path="/properties/:propertyId/edit" element={<PropertyFormPage />} />
      <Route path="/properties/:propertyId" element={<h1>Объект сохранён</h1>} />
    </Routes>, { initialRoute: '/properties/12/edit', queryClient })
    await screen.findByText(/Населённый пункт корпуса ещё не уточнён/)
    expect(screen.getByRole('combobox', { name: 'Населённый пункт' })).toHaveValue('')
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }))
    await screen.findByRole('heading', { name: 'Объект сохранён' })
    const submitted = writes.mock.calls.find(([, options]) => options?.method === 'PATCH')
    const payload = submitted?.[1].body as FormData
    expect(payload.get('buildingId')).toBe('6')
    expect(payload.has('localityId')).toBe(false)
    expect(payload.has('regionId')).toBe(false)
  })
})
