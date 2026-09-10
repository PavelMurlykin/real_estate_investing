import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type {
  SavedMortgageCalculationDetail,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { SavedMortgageCalculationDetailPage } from './SavedMortgageCalculationDetailPage'

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

const savedCalculation: SavedMortgageCalculationDetail = {
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
  legacyDetailUrl: '/mortgage/calculations/7/',
  legacySampleUrl: '/mortgage/?sample=7',
  calculation: {
    assumptions: {
      basePropertyCost: '5000000.00',
      priceAdjustmentType: 'discount',
      priceAdjustmentPercent: '10.00',
      priceAdjustmentRubles: '500000.00',
      finalPropertyCost: '4500000.00',
      initialPaymentPercent: '20.00',
      initialPaymentRubles: '900000.00',
      initialPaymentDate: '2026-09-09',
      mortgageTermMonths: 12,
      annualRate: '12.00',
      hasGracePeriod: false,
      gracePeriodTermMonths: 0,
      gracePeriodRate: null,
    },
    summary: {
      loanAmount: '3600000.00',
      mainMonthlyPayment: '319832.06',
      graceMonthlyPayment: null,
      overpayment: '237984.72',
      totalPayments: '3837984.72',
      paymentsCount: 12,
      mortgageEndDate: '2027-09-09',
      gracePeriodEndDate: null,
    },
    schedule: [
      {
        paymentNumber: 1,
        paymentDate: '2026-09-09',
        paymentAmount: '319832.06',
        interestAmount: '36000.00',
        principalAmount: '283832.06',
        remainingDebt: '3316167.94',
      },
    ],
  },
}

describe('SavedMortgageCalculationDetailPage', () => {
  it('renders property context, saved values and the payment schedule', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], authenticatedSession)
    queryClient.setQueryData(['saved-mortgage-calculation', 7], savedCalculation)

    renderWithProviders(
      <Routes>
        <Route
          path="/mortgage/calculations/:calculationId"
          element={<SavedMortgageCalculationDetailPage />}
        />
      </Routes>,
      { initialRoute: '/mortgage/calculations/7', queryClient },
    )

    expect(screen.getByRole('heading', { name: 'Зелёный квартал' })).toBeInTheDocument()
    expect(screen.getByText('Надёжный застройщик')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Параметры кредита' })).toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveAccessibleName(
      'График ежемесячных платежей',
    )
    expect(
      screen.getByRole('link', { name: 'Экспорт в прежней версии' }),
    ).toHaveAttribute('href', '/mortgage/calculations/7/')
  })

  it('keeps a direct private link behind authentication', () => {
    renderWithProviders(
      <Routes>
        <Route
          path="/mortgage/calculations/:calculationId"
          element={<SavedMortgageCalculationDetailPage />}
        />
      </Routes>,
      { initialRoute: '/mortgage/calculations/7' },
    )

    expect(
      screen.getByRole('heading', { name: 'Войдите, чтобы открыть расчёт' }),
    ).toBeInTheDocument()
  })
})
