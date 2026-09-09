import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  MortgageCalculationResponse,
  MortgageOptions,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { MortgageCalculatorPage } from './MortgageCalculatorPage'

const mortgageOptions: MortgageOptions = {
  defaultInitialPaymentDate: '2026-01-15',
  keyRate: '16.00',
  banks: [{ id: 1, name: 'Надёжный банк', logoUrl: '' }],
  programs: [
    {
      id: 10,
      bankId: 1,
      programId: 20,
      programName: 'Семейная ипотека',
      interestRate: '6.00',
      minimumInitialPaymentPercent: '25.00',
      maximumLoanTermYears: 20,
      isPreferential: true,
      creditLimit: '12000000.00',
      regionalCreditLimits: [],
    },
  ],
}

const mortgageResult: MortgageCalculationResponse = {
  assumptions: {
    basePropertyCost: '5000000.00',
    priceAdjustmentType: 'discount',
    priceAdjustmentPercent: '0.00',
    priceAdjustmentRubles: '0.00',
    finalPropertyCost: '5000000.00',
    initialPaymentPercent: '20.00',
    initialPaymentRubles: '1000000.00',
    initialPaymentDate: '2026-01-15',
    mortgageTermMonths: 360,
    annualRate: '15.00',
    hasGracePeriod: false,
    gracePeriodTermMonths: 0,
    gracePeriodRate: null,
  },
  summary: {
    loanAmount: '4000000.00',
    mainMonthlyPayment: '50577.51',
    graceMonthlyPayment: null,
    overpayment: '14207903.60',
    totalPayments: '18207903.60',
    paymentsCount: 360,
    mortgageEndDate: '2056-01-15',
    gracePeriodEndDate: null,
  },
  schedule: [
    {
      paymentNumber: 1,
      paymentDate: '2026-01-15',
      paymentAmount: '50577.51',
      interestAmount: '50000.00',
      principalAmount: '577.51',
      remainingDebt: '3999422.49',
    },
  ],
}

function renderCalculator() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['mortgage-options'], mortgageOptions)
  return renderWithProviders(<MortgageCalculatorPage />, { queryClient })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('MortgageCalculatorPage', () => {
  it('submits the form and renders summary and payment schedule', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mortgageResult), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderCalculator()

    await waitFor(() => {
      expect(screen.getByLabelText('Дата первого взноса')).toHaveValue(
        '2026-01-15',
      )
    })
    await user.click(screen.getByRole('button', { name: 'Рассчитать ипотеку' }))

    expect(
      await screen.findByRole('heading', { name: 'Параметры кредита' }),
    ).toBeInTheDocument()
    expect(
      screen.getAllByText(
        (_, element) => element?.textContent?.replace(/\s/g, '') === '50578₽',
        { selector: 'strong' },
      ),
    ).toHaveLength(2)
    expect(screen.getByRole('table')).toHaveAccessibleName(
      'График ежемесячных платежей',
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/mortgage/calculate/',
      expect.objectContaining({ method: 'POST', credentials: 'same-origin' }),
    )
  })

  it('applies selected bank program constraints to the form', async () => {
    const user = userEvent.setup()
    renderCalculator()

    await user.selectOptions(screen.getByLabelText('Банк'), '1')
    await user.selectOptions(screen.getByLabelText('Программа'), '10')

    expect(screen.getByLabelText('Годовая ставка, %')).toHaveValue(6)
    expect(screen.getByLabelText('Первоначальный взнос')).toHaveValue(25)
    expect(screen.getByLabelText('Срок ипотеки, месяцев')).toHaveValue(240)
  })

  it('shows authoritative server validation next to the affected field', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            initialPaymentValue: [
              'Первоначальный взнос не может превышать 100%.',
            ],
          }),
          {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      ),
    )
    renderCalculator()

    await waitFor(() => {
      expect(screen.getByLabelText('Дата первого взноса')).toHaveValue(
        '2026-01-15',
      )
    })
    const initialPaymentInput = screen.getByLabelText('Первоначальный взнос')
    await user.clear(initialPaymentInput)
    await user.type(initialPaymentInput, '101')
    await user.click(screen.getByRole('button', { name: 'Рассчитать ипотеку' }))

    expect(
      await screen.findByText(
        'Первоначальный взнос не может превышать 100%.',
      ),
    ).toBeInTheDocument()
    expect(initialPaymentInput).toHaveAttribute('aria-invalid', 'true')
  })
})
