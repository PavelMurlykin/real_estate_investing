import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { PropertyDetail, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { PropertyDetailPage } from './PropertyDetailPage'

const propertyDetail: PropertyDetail = {
  id: 1,
  apartmentNumber: '101',
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

function renderPropertyDetail(session?: Session) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['property', 1], propertyDetail)
  if (session) queryClient.setQueryData(['session'], session)
  return renderWithProviders(
    <Routes>
      <Route path="/properties/:propertyId" element={<PropertyDetailPage />} />
    </Routes>,
    { initialRoute: '/properties/1', queryClient },
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

  it('shows legacy edit and delete actions only to catalog managers', () => {
    renderPropertyDetail(administratorSession)

    expect(
      screen.getByRole('link', { name: 'Редактировать' }),
    ).toHaveAttribute('href', '/property/1/update/')
    expect(screen.getByRole('link', { name: 'Удалить' })).toHaveAttribute(
      'href',
      '/property/1/delete/',
    )
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
})
