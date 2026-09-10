import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  SavedTrenchMortgageCalculationDetail,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { SavedTrenchMortgageCalculationDetailPage } from './SavedTrenchMortgageCalculationDetailPage'

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

export const savedTrenchCalculation: SavedTrenchMortgageCalculationDetail = {
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
  legacyDetailUrl: '/mortgage/trench-calculations/17/',
  calculation: {
    assumptions: {
      basePropertyCost: '5000000.00',
      priceAdjustmentType: 'discount',
      priceAdjustmentPercent: '10.00',
      priceAdjustmentRubles: '500000.00',
      finalPropertyCost: '4500000.00',
      initialPaymentPercent: '20.00',
      initialPaymentRubles: '900000.00',
      initialPaymentDate: '2026-01-15',
      mortgageTermMonths: 24,
      annualRate: '12.00',
      trenchCount: 2,
    },
    summary: {
      loanAmount: '3600000.00',
      maximumMonthlyPayment: '190000.00',
      overpayment: '430000.00',
      totalPayments: '4030000.00',
      paymentsCount: 24,
      mortgageEndDate: '2028-01-15',
    },
    trenches: [
      {
        number: 1,
        date: '2026-01-15',
        percent: '40.00',
        amount: '1440000.00',
        annualRate: '12.00',
        monthlyPayment: '70000.00',
        paymentsCount: 6,
        remainingDebt: '2160000.00',
        overpayment: '180000.00',
      },
      {
        number: 2,
        date: '2026-07-15',
        percent: '60.00',
        amount: '2160000.00',
        annualRate: '10.00',
        monthlyPayment: '190000.00',
        paymentsCount: 18,
        remainingDebt: '0.00',
        overpayment: '250000.00',
      },
    ],
    schedule: [
      {
        paymentNumber: 1,
        paymentDate: '2026-01-15',
        paymentAmount: '70000.00',
        interestAmount: '14400.00',
        principalAmount: '55600.00',
        remainingDebt: '1384400.00',
      },
    ],
  },
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SavedTrenchMortgageCalculationDetailPage', () => {
  it('renders property context, tranches, schedule and export links', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], authenticatedSession)
    queryClient.setQueryData(
      ['saved-trench-mortgage-calculation', 17],
      savedTrenchCalculation,
    )

    renderWithProviders(
      <Routes>
        <Route
          path="/mortgage/trench/calculations/:calculationId"
          element={<SavedTrenchMortgageCalculationDetailPage />}
        />
      </Routes>,
      {
        initialRoute: '/mortgage/trench/calculations/17',
        queryClient,
      },
    )

    expect(
      screen.getByRole('heading', { name: 'Зелёный квартал' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('table', {
      name: 'Рассчитанные параметры траншей',
    })).toBeInTheDocument()
    expect(screen.getByRole('table', {
      name: 'Общий график ежемесячных платежей',
    })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Excel' })).toHaveAttribute(
      'href',
      '/api/v1/mortgage/trench/calculations/17/export/excel/',
    )
    expect(screen.getByRole('link', { name: 'Word' })).toHaveAttribute(
      'href',
      '/api/v1/mortgage/trench/calculations/17/export/word/',
    )
    expect(
      screen.getByRole('link', { name: 'Новый по образцу' }),
    ).toHaveAttribute('href', '/mortgage/trench?sample=17')
    expect(
      screen.getByRole('link', { name: 'Открыть Django-версию' }),
    ).toHaveAttribute('href', '/mortgage/trench-calculations/17/')
  })

  it('keeps a direct private link behind authentication', () => {
    renderWithProviders(
      <Routes>
        <Route
          path="/mortgage/trench/calculations/:calculationId"
          element={<SavedTrenchMortgageCalculationDetailPage />}
        />
      </Routes>,
      { initialRoute: '/mortgage/trench/calculations/17' },
    )

    expect(
      screen.getByRole('heading', { name: 'Войдите, чтобы открыть расчёт' }),
    ).toBeInTheDocument()
  })

  it('requires confirmation before deleting an owned calculation', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockImplementation(
      (_path: RequestInfo | URL, options?: RequestInit) => {
        if (options?.method === 'DELETE') {
          return Promise.resolve(new Response(null, { status: 204 }))
        }
        return Promise.resolve(
          new Response(JSON.stringify(savedTrenchCalculation), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      },
    )
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], authenticatedSession)
    queryClient.setQueryData(
      ['saved-trench-mortgage-calculation', 17],
      savedTrenchCalculation,
    )

    renderWithProviders(
      <Routes>
        <Route
          path="/mortgage/trench/calculations/:calculationId"
          element={<SavedTrenchMortgageCalculationDetailPage />}
        />
        <Route
          path="/mortgage/trench/calculations"
          element={<h1>История после удаления</h1>}
        />
      </Routes>,
      {
        initialRoute: '/mortgage/trench/calculations/17',
        queryClient,
      },
    )

    await user.click(screen.getByRole('button', { name: 'Удалить' }))

    expect(screen.getByRole('alertdialog')).toHaveAccessibleName(
      'Удалить сохранённый траншевый расчёт?',
    )
    const confirmButton = screen.getByRole('button', {
      name: 'Удалить расчёт',
    })
    expect(confirmButton).toHaveFocus()

    await user.click(confirmButton)

    expect(
      await screen.findByRole('heading', { name: 'История после удаления' }),
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/mortgage/trench/calculations/17/',
      expect.objectContaining({
        method: 'DELETE',
        credentials: 'same-origin',
      }),
    )
  })
})
