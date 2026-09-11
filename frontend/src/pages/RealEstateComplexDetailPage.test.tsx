import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { RealEstateComplexDetail, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { RealEstateComplexDetailPage } from './RealEstateComplexDetailPage'

const complexDetail: RealEstateComplexDetail = {
  id: 7,
  name: 'Белые ночи',
  description: 'Комплекс у парка',
  developerId: 4,
  developer: {
    id: 4,
    name: 'Северный девелопер',
    label: 'Северный девелопер (Группа Север)',
  },
  regionId: 1,
  region: 'Ленинградская область',
  cityId: 2,
  city: 'Санкт-Петербург',
  districtId: 3,
  district: 'Петроградский',
  realEstateClassId: 5,
  realEstateClass: 'Бизнес',
  realEstateTypeId: 6,
  realEstateType: 'Квартира',
  mapUrl: 'https://maps.example.com/complex',
  presentationUrl: null,
  investmentPotential: 'Стабильный спрос',
  photoUrl: '/media/property/complexes/photo.webp',
  buildings: [{
    id: 8,
    number: '1',
    address: 'Парковая улица, 1',
    commissioningDate: null,
    commissioningYear: 2028,
    commissioningQuarter: 2,
    commissioning: 'II кв. 2028',
    keyHandoverDate: '2028-09-01',
    keyHandoverYear: null,
    keyHandoverQuarter: null,
    keyHandover: '2028-09-01',
    propertyCount: 3,
    isActive: true,
  }],
  metroAvailability: [{
    id: 9,
    metroId: 10,
    station: 'Петроградская',
    line: 'Синяя',
    lineColor: '#0055aa',
    transportAccessibilityTypeId: 11,
    transportAccessibilityType: 'Пешком',
    walkingTimeMinutes: 12,
    isActive: true,
  }],
  isActive: true,
  createdAt: '2026-09-01T10:00:00+03:00',
  updatedAt: '2026-09-10T12:00:00+03:00',
  legacyDetailUrl: '/property/complexes/7/',
  legacyEditUrl: '/property/complexes/7/update/',
  legacyDeleteUrl: '/property/complexes/7/delete/',
}

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

function renderDetail(session?: Session) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['real-estate-complex', 7], complexDetail)
  if (session) queryClient.setQueryData(['session'], session)
  return renderWithProviders(
    <Routes>
      <Route path="/complexes/:complexId" element={<RealEstateComplexDetailPage />} />
    </Routes>,
    { initialRoute: '/complexes/7', queryClient },
  )
}

describe('RealEstateComplexDetailPage', () => {
  it('shows the public card, related rows, and accessible photo dialog', async () => {
    const user = userEvent.setup()
    renderDetail()

    expect(screen.getByRole('heading', { name: 'Белые ночи' }))
      .toBeInTheDocument()
    expect(screen.getByText('Парковая улица, 1')).toBeInTheDocument()
    expect(screen.getByText('Петроградская')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Удалить' }))
      .not.toBeInTheDocument()

    await user.click(screen.getByRole('button', {
      name: 'Увеличить фото жилого комплекса',
    }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAccessibleName('Фото Белые ночи')
    expect(within(dialog).getByRole('button', {
      name: 'Закрыть изображение',
    })).toHaveFocus()
  })

  it('shows management actions and a linked-object conflict', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Связаны объекты.' }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      }),
    ))
    renderDetail(managerSession)

    expect(screen.getByRole('link', { name: 'Редактировать' }))
      .toHaveAttribute('href', '/complexes/7/edit')
    await user.click(screen.getByRole('button', { name: 'Удалить' }))
    await user.click(within(screen.getByRole('alertdialog')).getByRole(
      'button',
      { name: 'Удалить' },
    ))

    expect(await screen.findByText(
      'ЖК нельзя удалить, пока с его корпусами связаны объекты.',
    )).toBeInTheDocument()
  })
})
