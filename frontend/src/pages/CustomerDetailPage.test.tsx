import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { CustomerDetail, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { CustomerDetailPage } from './CustomerDetailPage'

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

function renderCustomerDetail(session?: Session) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['customer', 12], customerDetail)
  if (session) queryClient.setQueryData(['session'], session)
  return renderWithProviders(
    <Routes>
      <Route path="/customers/:customerId" element={<CustomerDetailPage />} />
    </Routes>,
    { initialRoute: '/customers/12', queryClient },
  )
}

describe('CustomerDetailPage', () => {
  it('prompts anonymous visitors to sign in without exposing cached data', () => {
    renderCustomerDetail()

    expect(
      screen.getByRole('heading', {
        name: 'Войдите, чтобы открыть карточку клиента',
      }),
    ).toBeInTheDocument()
    expect(screen.queryByText('Иван Петров')).not.toBeInTheDocument()
  })

  it('renders profile, preferences and authoritative financial capacity', () => {
    renderCustomerDetail(authenticatedSession)

    expect(
      screen.getByRole('heading', { name: 'Иван Петров' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Финансовый потенциал' }),
    ).toBeInTheDocument()
    expect(screen.getByText('17 500 000 ₽')).toBeInTheDocument()
    expect(screen.getByText('14 000 000 ₽')).toBeInTheDocument()
    expect(screen.getByText('Семейная ипотека')).toBeInTheDocument()
    expect(screen.getByText('Евро-3')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Рассчитать ипотеку' }),
    ).toHaveAttribute('href', '/mortgage/?customer=12')
    expect(
      screen.getByRole('link', { name: 'Django-версии карточки' }),
    ).toHaveAttribute('href', '/customers/12/')
  })

  it('handles an invalid direct route without requesting private data', () => {
    renderWithProviders(
      <Routes>
        <Route path="/customers/:customerId" element={<CustomerDetailPage />} />
      </Routes>,
      { initialRoute: '/customers/not-a-number' },
    )

    expect(
      screen.getByRole('heading', { name: 'Клиент не найден' }),
    ).toBeInTheDocument()
  })
})
