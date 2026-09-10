import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type {
  SavedMortgageCalculationListResponse,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { SavedMortgageCalculationListPage } from './SavedMortgageCalculationListPage'

const authenticatedSession: Session = {
  isAuthenticated: true,
  user: {
    id: 1,
    displayName: 'Анна Смирнова',
    email: 'anna@example.com',
    agencyName: '',
  },
  capabilities: {
    manageCatalogs: false,
    syncExternalData: false,
    viewPrivateRecords: true,
    viewAllPrivateRecords: false,
  },
}

const calculationHistory: SavedMortgageCalculationListResponse = {
  page: 1,
  pageSize: 20,
  totalCount: 1,
  totalPages: 1,
  results: [
    {
      id: 7,
      createdAt: '2026-09-09T10:30:00+03:00',
      property: {
        id: 3,
        city: 'Казань',
        developer: 'Надёжный застройщик',
        realEstateComplex: 'Зелёный квартал',
        realEstateClass: 'Комфорт',
        building: '2',
        apartmentNumber: '42',
        layout: 'Евродвушка',
        decoration: 'Чистовая',
        area: '52.40',
        floor: 8,
        detailUrl: '/property/3/',
      },
      finalPropertyCost: '4500000.00',
      initialPaymentRubles: '900000.00',
      mainMonthlyPayment: '319832.06',
      mortgageTermMonths: 12,
      annualRate: '12.00',
    },
  ],
}

describe('SavedMortgageCalculationListPage', () => {
  it('does not request private data and prompts anonymous visitors to sign in', () => {
    renderWithProviders(<SavedMortgageCalculationListPage />)

    expect(
      screen.getByRole('heading', { name: 'Войдите, чтобы открыть историю' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Войти' })).toHaveAttribute(
      'href',
      '/users/login/?next=%2Fapp%2Fmortgage%2Fcalculations',
    )
  })

  it('renders the owner history in desktop and mobile layouts', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], authenticatedSession)
    queryClient.setQueryData(
      ['saved-mortgage-calculations', ''],
      calculationHistory,
    )

    renderWithProviders(<SavedMortgageCalculationListPage />, { queryClient })

    expect(
      screen.getByRole('heading', { name: 'История расчётов ипотеки' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveAccessibleName(
      'История ипотечных расчётов',
    )
    expect(screen.getAllByText('Зелёный квартал')).toHaveLength(2)
    expect(
      screen.getAllByRole('link', { name: /Открыть расчёт/ })[0],
    ).toHaveAttribute('href', '/mortgage/calculations/7')
  })
})
