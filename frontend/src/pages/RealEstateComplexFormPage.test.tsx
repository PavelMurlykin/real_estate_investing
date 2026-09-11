import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type {
  RealEstateComplexDetail,
  RealEstateComplexOptions,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { RealEstateComplexFormPage } from './RealEstateComplexFormPage'

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

const formOptions: RealEstateComplexOptions = {
  regions: [{ id: 1, name: 'Ленинградская область' }],
  cities: [{ id: 2, name: 'Санкт-Петербург' }],
  districts: [{ id: 3, name: 'Петроградский' }],
  developers: [{ id: 4, label: 'Северный девелопер' }],
  realEstateClasses: [{ id: 5, name: 'Бизнес' }],
  realEstateTypes: [{ id: 6, name: 'Квартира' }],
  transportAccessibilityTypes: [{ id: 8, name: 'Пешком' }],
  metroStations: [{
    id: 7,
    station: 'Петроградская',
    line: 'Синяя',
    lineColor: '#0055aa',
  }],
  quarters: [
    { value: 1, label: 'I кв.' },
    { value: 2, label: 'II кв.' },
    { value: 3, label: 'III кв.' },
    { value: 4, label: 'IV кв.' },
  ],
  truncated: {
    regions: false,
    cities: false,
    districts: false,
    developers: false,
    realEstateClasses: false,
    realEstateTypes: false,
    transportAccessibilityTypes: false,
    metroStations: false,
  },
}

const savedComplex: RealEstateComplexDetail = {
  id: 99,
  name: 'Новый квартал',
  description: '',
  developerId: 4,
  developer: { id: 4, name: 'Северный девелопер', label: 'Северный девелопер' },
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
  mapUrl: null,
  presentationUrl: null,
  investmentPotential: '',
  photoUrl: null,
  buildings: [{
    id: 10,
    number: '1',
    address: null,
    commissioningDate: null,
    commissioningYear: null,
    commissioningQuarter: null,
    commissioning: null,
    keyHandoverDate: null,
    keyHandoverYear: null,
    keyHandoverQuarter: null,
    keyHandover: null,
    propertyCount: 0,
    isActive: true,
  }],
  metroAvailability: [{
    id: 11,
    metroId: 7,
    station: 'Петроградская',
    line: 'Синяя',
    lineColor: '#0055aa',
    transportAccessibilityTypeId: 8,
    transportAccessibilityType: 'Пешком',
    walkingTimeMinutes: 10,
    isActive: true,
  }],
  isActive: true,
  createdAt: '2026-09-11T10:00:00+03:00',
  updatedAt: '2026-09-11T10:00:00+03:00',
  legacyDetailUrl: '/property/complexes/99/',
  legacyEditUrl: '/property/complexes/99/update/',
  legacyDeleteUrl: '/property/complexes/99/delete/',
}

function createManagerQueryClient() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['session'], managerSession)
  for (const queryString of ['', 'regionId=1', 'regionId=1&cityId=2']) {
    queryClient.setQueryData(
      ['real-estate-complex-options', queryString],
      formOptions,
    )
  }
  return queryClient
}

function renderCreateForm() {
  return renderWithProviders(
    <Routes>
      <Route path="/complexes/new" element={<RealEstateComplexFormPage />} />
      <Route path="/complexes/:complexId" element={<h1>ЖК сохранён</h1>} />
    </Routes>,
    { initialRoute: '/complexes/new', queryClient: createManagerQueryClient() },
  )
}

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Название ЖК *'), 'Новый квартал')
  await user.selectOptions(screen.getByLabelText('Застройщик *'), '4')
  await user.selectOptions(screen.getByLabelText('Класс ЖК *'), '5')
  await user.selectOptions(screen.getByLabelText('Тип недвижимости *'), '6')
  await user.selectOptions(screen.getByLabelText('Регион *'), '1')
  await user.selectOptions(screen.getByLabelText('Город *'), '2')
  await user.selectOptions(screen.getByLabelText('Район *'), '3')
  await user.type(screen.getByLabelText('Номер корпуса 1 *'), '1')
  await user.click(screen.getByRole('button', { name: 'Добавить станцию' }))
  await user.selectOptions(screen.getByLabelText('Станция метро 1 *'), '7')
  await user.selectOptions(screen.getByLabelText('Способ *'), '8')
  await user.type(screen.getByLabelText('Время, мин. *'), '10')
}

describe('RealEstateComplexFormPage', () => {
  it('does not expose mutations to users without catalog permissions', () => {
    renderWithProviders(
      <Routes>
        <Route path="/complexes/new" element={<RealEstateComplexFormPage />} />
      </Routes>,
      { initialRoute: '/complexes/new' },
    )

    expect(screen.getByRole('heading', { name: 'Недостаточно прав' }))
      .toBeInTheDocument()
  })

  it('creates a complete complex through multipart API', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(savedComplex), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderCreateForm()

    await fillRequiredFields(user)
    await user.click(screen.getByRole('button', { name: 'Создать ЖК' }))

    expect(await screen.findByRole('heading', { name: 'ЖК сохранён' }))
      .toBeInTheDocument()
    const [requestPath, requestOptions] = fetchMock.mock.calls[0] as [
      string,
      RequestInit,
    ]
    expect(requestPath).toBe('/api/v1/complexes/')
    expect(requestOptions.method).toBe('POST')
    const formData = requestOptions.body as FormData
    expect(formData.get('name')).toBe('Новый квартал')
    expect(JSON.parse(String(formData.get('buildings')))).toEqual([
      expect.objectContaining({ number: '1' }),
    ])
    expect(JSON.parse(String(formData.get('metroAvailability')))).toEqual([
      expect.objectContaining({ metroId: 7, walkingTimeMinutes: 10 }),
    ])
  })

  it('shows the authoritative API name error without clearing the form', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        name: ['ЖК с таким названием у застройщика уже существует.'],
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    ))
    renderCreateForm()

    await fillRequiredFields(user)
    await user.click(screen.getByRole('button', { name: 'Создать ЖК' }))

    expect(await screen.findByText(
      'ЖК с таким названием у застройщика уже существует.',
    )).toBeInTheDocument()
    expect(screen.getByLabelText(/^Название ЖК \*/)).toHaveValue('Новый квартал')
  })
})
