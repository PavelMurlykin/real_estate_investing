import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { PropertyDetail, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { PropertyDetailPage } from './PropertyDetailPage'

const propertyDetail: PropertyDetail = {
  id: 1,
  apartmentNumber: '101',
  regionId: 1,
  cityId: 2,
  districtId: 3,
  developerId: 4,
  realEstateComplexId: 5,
  buildingId: 6,
  layoutId: 7,
  decorationId: 8,
  windowViewIds: [9, 10],
  developer: 'Северный девелопер (Группа Север)',
  realEstateComplex: 'Белые ночи',
  realEstateClass: 'Бизнес',
  realEstateType: 'Квартира',
  district: 'Петроградский',
  city: 'Санкт-Петербург',
  region: 'Ленинградская область',
  building: '1',
  buildingAddress: 'Петровский проспект, 10',
  commissioning: 'II кв. 2027',
  keyHandover: '2027-09-01',
  layout: 'Евродвушка',
  layoutDescription: 'Кухня-гостиная и отдельная спальня',
  decoration: 'Чистовая',
  decorationDescription: null,
  windowViews: ['Парк', 'Двор'],
  area: '42.50',
  floor: 10,
  propertyCost: '12500000.00',
  mapUrl: 'https://maps.example.com/complex',
  presentationUrl: 'https://files.example.com/presentation.pdf',
  images: [
    {
      kind: 'layout',
      label: 'Планировка',
      url: '/media/property/layouts/layout.webp',
    },
    {
      kind: 'floorPlan',
      label: 'План этажа',
      url: null,
    },
    {
      kind: 'windowView',
      label: 'Вид из окна',
      url: '/media/property/window_views/view.webp',
    },
  ],
  createdAt: '2026-09-01T10:00:00+03:00',
  updatedAt: '2026-09-09T12:30:00+03:00',
  legacyDetailUrl: '/property/1/',
  legacyEditUrl: '/property/1/update/',
  legacyDeleteUrl: '/property/1/delete/',
}

const administratorSession: Session = {
  isAuthenticated: true,
  user: {
    id: 7,
    displayName: 'Администратор',
    email: 'admin@example.com',
    agencyName: '',
  },
  capabilities: {
    manageCatalogs: true,
    syncExternalData: true,
    viewPrivateRecords: true,
    viewAllPrivateRecords: true,
  },
}

function renderPropertyDetail(session?: Session, initialRoute = '/properties/1') {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['property', 1], propertyDetail)
  if (session) queryClient.setQueryData(['session'], session)
  return renderWithProviders(
    <Routes>
      <Route path="/properties/:propertyId" element={<PropertyDetailPage />} />
      <Route path="/properties" element={<h1>Каталог объектов</h1>} />
    </Routes>,
    { initialRoute, queryClient },
  )
}

describe('PropertyDetailPage', () => {
  it('renders the complete property card and an accessible image preview', async () => {
    const user = userEvent.setup()
    renderPropertyDetail()

    expect(
      screen.getByRole('heading', {
        name: 'Белые ночи, квартира 101',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('Парк, Двор')).toBeInTheDocument()
    expect(screen.getByText('01.09.2027')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Рассчитать ипотеку' }),
    ).toHaveAttribute(
      'href',
      '/mortgage?propertyId=1&propertyCost=12500000.00',
    )
    expect(
      screen.getByRole('link', { name: /Открыть на карте/ }),
    ).toHaveAttribute('href', 'https://maps.example.com/complex')
    expect(screen.getByText('Не загружено')).toBeInTheDocument()

    const imageTrigger = screen.getByRole('button', {
      name: 'Увеличить: Планировка',
    })
    await user.click(imageTrigger)

    expect(screen.getByRole('dialog')).toHaveAccessibleName('Планировка')
    expect(
      screen.getByRole('button', { name: 'Закрыть изображение' }),
    ).toHaveFocus()

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await waitFor(() => expect(imageTrigger).toHaveFocus())
  })

  it('routes catalog managers to React editing and confirms deletion', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, { status: 204 }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderPropertyDetail(administratorSession)

    expect(
      screen.getByRole('link', { name: 'Редактировать' }),
    ).toHaveAttribute('href', '/properties/1/edit')

    await user.click(screen.getByRole('button', { name: 'Удалить' }))
    expect(screen.getByRole('alertdialog')).toHaveAccessibleName(
      'Удалить объект?',
    )
    expect(screen.getByRole('button', { name: 'Отмена' })).toHaveFocus()

    await user.click(
      screen.getAllByRole('button', { name: 'Удалить' }).at(-1)!,
    )
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/properties/1/',
      expect.objectContaining({ method: 'DELETE' }),
    ))
  })

  it('handles an invalid direct route without requesting the API', () => {
    renderWithProviders(
      <Routes>
        <Route path="/properties/:propertyId" element={<PropertyDetailPage />} />
      </Routes>,
      { initialRoute: '/properties/not-a-number' },
    )

    expect(
      screen.getByRole('heading', { name: 'Объект не найден' }),
    ).toBeInTheDocument()
  })

  it('keeps the customer context in catalog and calculator navigation', () => {
    renderPropertyDetail(undefined, '/properties/1?customerId=12')

    expect(screen.getByRole('link', { name: 'К каталогу' })).toHaveAttribute(
      'href',
      '/properties?customerId=12',
    )
    expect(
      screen.getByRole('link', { name: 'Рассчитать ипотеку' }),
    ).toHaveAttribute(
      'href',
      '/mortgage?propertyId=1&propertyCost=12500000.00&customerId=12',
    )
  })
})
