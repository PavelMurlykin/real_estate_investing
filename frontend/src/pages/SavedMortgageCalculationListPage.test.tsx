import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

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
      isLinked: false,
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
      '/app/login?next=%2Fapp%2Fmortgage%2Fcalculations',
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

  it('adds selected saved calculations to a customer', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        createdCount: 1,
        linkedCalculationIds: [7],
      }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], authenticatedSession)
    queryClient.setQueryData(
      ['saved-mortgage-calculations', 'customerId=12'],
      calculationHistory,
    )

    renderWithProviders(
      <Routes>
        <Route
          path="/mortgage/calculations"
          element={<SavedMortgageCalculationListPage />}
        />
        <Route path="/customers/:customerId" element={<h1>Карточка клиента</h1>} />
      </Routes>,
      {
      initialRoute: '/mortgage/calculations?customerId=12',
      queryClient,
      },
    )

    await user.click(screen.getByRole('checkbox', {
      name: /Добавить расчёт от .* клиенту/,
    }))
    await user.click(screen.getByRole('button', { name: 'Добавить клиенту' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/customers/12/calculations/',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      programType: 'market',
      calculationIds: [7],
    })
  })
})
