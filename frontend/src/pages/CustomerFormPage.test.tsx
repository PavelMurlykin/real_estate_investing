import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  CustomerDetail,
  CustomerFormOptions,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { CustomerFormPage } from './CustomerFormPage'

const authenticatedSession: Session = {
  isAuthenticated: true,
  user: {
    id: 1,
    displayName: 'Анна Агент',
    email: 'agent@example.com',
    agencyName: 'Север',
  },
  capabilities: {
    manageCatalogs: false,
    syncExternalData: false,
    viewPrivateRecords: true,
    viewAllPrivateRecords: false,
  },
}

const formOptions: CustomerFormOptions = {
  cities: [
    { id: 1, name: 'Химки' },
    { id: 2, name: 'Москва' },
  ],
  districts: [{ id: 4, name: 'Хамовники' }],
  layouts: [{ id: 5, name: 'Евро-3' }],
  preferentialPrograms: [{ id: 3, name: 'Семейная ипотека' }],
  purchaseGoals: [
    { value: 'living', label: 'Для жизни' },
    { value: 'investment', label: 'Для инвестиций' },
  ],
  cardinalDirections: [
    { value: 'Юг', label: 'Юг' },
    { value: 'Восток', label: 'Восток' },
  ],
  truncated: {
    cities: false,
    districts: false,
    layouts: false,
    preferentialPrograms: false,
  },
}

const customerDetail: CustomerDetail = {
  id: 12,
  firstName: 'Иван',
  lastName: 'Петров',
  fullName: 'Иван Петров',
  phone: '+79995554433',
  email: 'ivan@example.com',
  age: 35,
  birthDate: '1991-02-10',
  birthYear: 1991,
  residenceCity: 'Химки',
  residenceCityId: 1,
  initialPaymentAmount: '2000000.00',
  maximumMonthlyPayment: '150000.00',
  preferentialPrograms: [{ id: 3, name: 'Семейная ипотека' }],
  hasOwnedProperty: false,
  purchaseGoal: 'investment',
  purchaseGoalLabel: 'Для инвестиций',
  desiredCity: 'Москва',
  desiredCityId: 2,
  desiredDistrict: 'Хамовники',
  desiredDistrictId: 4,
  desiredLayouts: [{ id: 5, name: 'Евро-3' }],
  areaMinimum: '55.00',
  areaMaximum: '80.00',
  desiredFloor: 'Не первый',
  cardinalDirections: 'Юг, Восток',
  comment: 'Нужен тихий двор',
  calculated: {
    maximumTermYears: 30,
    actualKeyRate: '16.00',
    annualRate: '18.00',
    maximumPropertyCost: '17500000.00',
    hasPreferentialProgram: true,
    preferentialAnnualRate: '6.00',
    preferentialMaximumPropertyCost: '14000000.00',
    preferentialCreditLimit: '12000000.00',
  },
  isActive: true,
  createdAt: '2026-09-01T10:00:00+03:00',
  updatedAt: '2026-09-09T12:30:00+03:00',
  legacyDetailUrl: '/customers/12/',
  legacyEditUrl: '/customers/12/update/',
  legacyDeleteUrl: '/customers/12/delete/',
  legacyMortgageUrl: '/mortgage/?customer=12',
}

function createAuthenticatedQueryClient() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['session'], authenticatedSession)
  queryClient.setQueryData(['customer-form-options', ''], formOptions)
  return queryClient
}

function renderCreateForm() {
  const queryClient = createAuthenticatedQueryClient()
  return renderWithProviders(
    <Routes>
      <Route path="/customers/new" element={<CustomerFormPage />} />
      <Route
        path="/customers/:customerId"
        element={<h1>Карточка клиента сохранена</h1>}
      />
    </Routes>,
    { initialRoute: '/customers/new', queryClient },
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('CustomerFormPage', () => {
  it('prompts anonymous visitors to sign in', () => {
    renderWithProviders(
      <Routes>
        <Route path="/customers/new" element={<CustomerFormPage />} />
      </Routes>,
      { initialRoute: '/customers/new' },
    )

    expect(
      screen.getByRole('heading', {
        name: 'Войдите, чтобы работать с клиентами',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Войти' })).toHaveAttribute(
      'href',
      '/app/login?next=%2Fapp%2Fcustomers%2Fnew',
    )
  })

  it('prefills every relation-backed field for editing', async () => {
    const queryClient = createAuthenticatedQueryClient()
    queryClient.setQueryData(['customer', 12], customerDetail)
    queryClient.setQueryData(['customer-form-options', '2'], formOptions)

    renderWithProviders(
      <Routes>
        <Route
          path="/customers/:customerId/edit"
          element={<CustomerFormPage />}
        />
      </Routes>,
      { initialRoute: '/customers/12/edit', queryClient },
    )

    expect(await screen.findByLabelText('Имя *')).toHaveValue('Иван')
    expect(screen.getByLabelText('Семейная ипотека')).toBeChecked()
    expect(screen.getByLabelText('Евро-3')).toBeChecked()
    expect(
      screen.getByRole('combobox', { name: 'Желаемый район' }),
    ).toHaveValue('4')
    expect(screen.getByRole('link', { name: 'Django-форма' })).toHaveAttribute(
      'href',
      '/customers/12/update/',
    )
  })

  it('creates a customer, prevents duplicate submission and opens its card', async () => {
    const user = userEvent.setup()
    let resolveRequest: ((response: Response) => void) | undefined
    const fetchMock = vi.fn<typeof fetch>(
      () => new Promise<Response>((resolve) => {
        resolveRequest = resolve
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderCreateForm()

    await user.type(screen.getByLabelText('Имя *'), 'Мария')
    await user.click(screen.getByRole('button', { name: 'Сохранить клиента' }))

    expect(
      screen.getByRole('button', { name: 'Сохраняем…' }),
    ).toBeDisabled()
    resolveRequest?.(
      new Response(JSON.stringify({ id: 99 }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    expect(
      await screen.findByRole('heading', {
        name: 'Карточка клиента сохранена',
      }),
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/customers/')
    const requestOptions = fetchMock.mock.calls[0][1] as RequestInit
    expect(JSON.parse(requestOptions.body as string)).toMatchObject({
      firstName: 'Мария',
      preferentialProgramIds: [],
      desiredLayoutIds: [],
    })
  })

  it('shows authoritative server errors beside their fields', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            areaMaximum: [
              'Максимальная площадь должна быть не меньше минимальной.',
            ],
          }),
          {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      ),
    )
    renderCreateForm()

    await user.type(screen.getByLabelText('Имя *'), 'Мария')
    await user.click(screen.getByRole('button', { name: 'Сохранить клиента' }))

    expect(
      await screen.findByText(
        'Максимальная площадь должна быть не меньше минимальной.',
      ),
    ).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByRole('spinbutton', {
        name: /Площадь до, м²/,
      })).toHaveAttribute(
        'aria-invalid',
        'true',
      )
    })
  })
})
