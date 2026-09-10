import { screen } from '@testing-library/react'
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
  regions: [{ id: 1, name: 'Ленинградская область' }],
  cities: [{ id: 2, name: 'Санкт-Петербург' }],
  districts: [{ id: 3, name: 'Петроградский' }],
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

const optionQueryStrings = [
  '',
  'regionId=1',
  'regionId=1&cityId=2',
  'regionId=1&cityId=2&districtId=3',
  'regionId=1&cityId=2&districtId=3&developerId=4',
  (
    'regionId=1&cityId=2&districtId=3&developerId=4'
    + '&realEstateComplexId=5'
  ),
]

function createManagerQueryClient() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['session'], managerSession)
  optionQueryStrings.forEach((queryString) => {
    queryClient.setQueryData(
      ['property-form-options', queryString],
      formOptions,
    )
  })
  return queryClient
}

function renderCreateForm() {
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
  await user.selectOptions(screen.getByLabelText('Регион *'), '1')
  await user.selectOptions(screen.getByLabelText('Город *'), '2')
  await user.selectOptions(screen.getByLabelText('Район *'), '3')
  await user.selectOptions(screen.getByLabelText('Застройщик *'), '4')
  await user.selectOptions(screen.getByLabelText('Жилой комплекс *'), '5')
  await user.selectOptions(screen.getByLabelText('Корпус *'), '6')
  await user.type(screen.getByLabelText('Номер квартиры *'), '303')
  await user.type(screen.getByLabelText('Площадь, м² *'), '61.25')
  await user.type(screen.getByLabelText('Этаж *'), '12')
  await user.type(screen.getByLabelText('Стоимость, ₽ *'), '19000000')
  await user.selectOptions(screen.getByLabelText('Планировка *'), '7')
  await user.selectOptions(screen.getByLabelText('Отделка *'), '8')
  await user.click(screen.getByLabelText('Парк'))
}

describe('PropertyFormPage', () => {
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
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [requestPath, requestOptions] = fetchMock.mock.calls[0] as [
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
    renderWithProviders(
      <Routes>
        <Route path="/properties/:propertyId/edit" element={<PropertyFormPage />} />
        <Route path="/properties/:propertyId" element={<h1>Объект сохранён</h1>} />
      </Routes>,
      { initialRoute: '/properties/12/edit', queryClient },
    )

    expect(await screen.findByLabelText('Номер квартиры *')).toHaveValue('101')
    expect(screen.getByLabelText('Парк')).toBeChecked()
    expect(screen.getByRole('link', { name: 'Django-форма' })).toHaveAttribute(
      'href',
      '/property/12/update/',
    )
    await user.click(screen.getByRole('button', { name: 'Удалить текущее' }))
    await user.click(
      screen.getByRole('button', { name: 'Сохранить изменения' }),
    )

    await screen.findByRole('heading', { name: 'Объект сохранён' })
    const requestOptions = fetchMock.mock.calls[0][1] as RequestInit
    const formData = requestOptions.body as FormData
    expect(requestOptions.method).toBe('PATCH')
    expect(formData.get('clearLayoutImage')).toBe('true')
  })
})
