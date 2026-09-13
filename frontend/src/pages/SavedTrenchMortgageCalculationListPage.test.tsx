import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type {
  SavedTrenchMortgageCalculationListResponse,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { SavedTrenchMortgageCalculationListPage } from './SavedTrenchMortgageCalculationListPage'

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

const calculationHistory: SavedTrenchMortgageCalculationListResponse = {
  page: 1,
  pageSize: 20,
  totalCount: 1,
  totalPages: 1,
  results: [
    {
      id: 17,
      createdAt: '2026-09-10T10:30:00+03:00',
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
      maximumMonthlyPayment: '190000.00',
      mortgageTermMonths: 24,
      annualRate: '12.00',
      trenchCount: 2,
      isLinked: false,
    },
  ],
}

describe('SavedTrenchMortgageCalculationListPage', () => {
  it('keeps anonymous visitors away from private history requests', () => {
    renderWithProviders(<SavedTrenchMortgageCalculationListPage />)

    expect(
      screen.getByRole('heading', { name: 'Войдите, чтобы открыть историю' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Войти' })).toHaveAttribute(
      'href',
      '/app/login?next=%2Fapp%2Fmortgage%2Ftrench%2Fcalculations',
    )
  })

  it('renders owner history in desktop and mobile layouts', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], authenticatedSession)
    queryClient.setQueryData(
      ['saved-trench-mortgage-calculations', ''],
      calculationHistory,
    )

    renderWithProviders(<SavedTrenchMortgageCalculationListPage />, {
      queryClient,
    })

    expect(
      screen.getByRole('heading', { name: 'История траншевой ипотеки' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveAccessibleName(
      'История траншевых ипотечных расчётов',
    )
    expect(screen.getAllByText('Зелёный квартал')).toHaveLength(2)
    expect(
      screen.getAllByRole('link', { name: /Открыть расчёт/ })[0],
    ).toHaveAttribute('href', '/mortgage/trench/calculations/17')
  })
})
