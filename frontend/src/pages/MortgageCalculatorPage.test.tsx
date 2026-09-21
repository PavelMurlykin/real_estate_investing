import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  MortgageCalculationResponse,
  MortgageOptions,
  SavedMortgageCalculationDetail,
  Session,
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

const propertyList = {
  page: 1,
  pageSize: 100,
  totalCount: 1,
  totalPages: 1,
  results: [{
    id: 3,
    city: 'Казань',
    developer: 'Надёжный застройщик',
    realEstateComplex: 'Зелёный квартал',
    building: '2',
    apartmentNumber: '42',
    layout: 'Евродвушка',
    decoration: 'Чистовая',
    area: '52.40',
    floor: 8,
    propertyCost: '5000000.00',
    detailUrl: '/property/3/',
  }],
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
    ...mortgageResult,
    assumptions: {
      ...mortgageResult.assumptions,
      basePropertyCost: '6300000.00',
      priceAdjustmentType: 'markup',
      priceAdjustmentPercent: '7.50',
      priceAdjustmentRubles: '472500.00',
      finalPropertyCost: '6772500.00',
      initialPaymentPercent: '35.00',
      initialPaymentRubles: '2370375.00',
      initialPaymentDate: '2026-10-20',
      mortgageTermMonths: 180,
      annualRate: '8.25',
      hasGracePeriod: true,
      gracePeriodTermMonths: 24,
      gracePeriodRate: '5.25',
    },
  },
}

function renderCalculator({
  initialRoute = '/',
  savedSample,
  session,
}: {
  initialRoute?: string
  savedSample?: SavedMortgageCalculationDetail
  session?: Session
} = {}) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['mortgage-options'], mortgageOptions)
  queryClient.setQueryData(
    ['properties', 'pageSize=100&ordering=realEstateComplex'],
    propertyList,
  )
  if (session) queryClient.setQueryData(['session'], session)
  if (savedSample) {
    queryClient.setQueryData(
      ['saved-mortgage-calculation', savedSample.id],
      savedSample,
    )
  }
  return renderWithProviders(<MortgageCalculatorPage />, {
    initialRoute,
    queryClient,
  })
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
      expect(screen.getByLabelText('Дата первоначального взноса')).toHaveValue(
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
    await user.selectOptions(screen.getByLabelText('Ипотечная программа'), '10')

    expect(screen.getByLabelText('Годовая ставка, %')).toHaveValue(6)
    expect(screen.getByLabelText('Первоначальный взнос, %')).toHaveValue(25)
    expect(screen.getByLabelText('Срок ипотеки, месяцев')).toHaveValue(240)
  })

  it('keeps shared object data and synchronized values visible in both modes', async () => {
    const user = userEvent.setup()
    renderCalculator()

    expect(screen.getByRole('heading', { name: 'Данные объекта' })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Объект недвижимости'), '3')

    expect(screen.getByLabelText('Город')).toHaveValue('Казань')
    expect(screen.getByLabelText('Базовая стоимость, ₽')).toHaveValue(5000000)

    const adjustmentPercent = screen.getByLabelText('Скидка, %')
    await user.clear(adjustmentPercent)
    await user.type(adjustmentPercent, '10')
    expect(screen.getByLabelText('Скидка, ₽')).toHaveValue(500000)
    expect(screen.getByLabelText('Первоначальный взнос, ₽')).toHaveValue(900000)

    const adjustmentRubles = screen.getByLabelText('Скидка, ₽')
    await user.clear(adjustmentRubles)
    await user.type(adjustmentRubles, '250000')
    expect(adjustmentPercent).toHaveValue(5)

    const mortgageTermYears = screen.getByLabelText('Срок ипотеки, лет')
    await user.clear(mortgageTermYears)
    await user.type(mortgageTermYears, '20')
    expect(screen.getByLabelText('Срок ипотеки, месяцев')).toHaveValue(240)

    const mortgageTermMonths = screen.getByLabelText('Срок ипотеки, месяцев')
    await user.clear(mortgageTermMonths)
    await user.type(mortgageTermMonths, '180')
    expect(mortgageTermYears).toHaveValue(15)

    await user.click(screen.getByLabelText('Траншевая ипотека'))
    expect(screen.getByLabelText('Количество траншей')).toBeInTheDocument()
    expect(screen.getByLabelText('Базовая стоимость, ₽')).toHaveValue(5000000)
    expect(screen.getByLabelText('Город')).toHaveValue('Казань')
  })

  it('loads a private saved scenario as a new React calculation sample', async () => {
    renderCalculator({
      initialRoute: '/?sample=7',
      savedSample: savedCalculation,
      session: authenticatedSession,
    })

    await waitFor(() => {
      expect(screen.getByLabelText('Базовая стоимость, ₽')).toHaveValue(6300000)
    })
    expect(screen.getByLabelText('Удорожание')).toBeChecked()
    expect(screen.getByLabelText('Удорожание, %')).toHaveValue(7.5)
    expect(screen.getByLabelText('Первоначальный взнос, %')).toHaveValue(35)
    expect(screen.getByLabelText('Дата первоначального взноса')).toHaveValue(
      '2026-10-20',
    )
    expect(screen.getByLabelText('Срок ипотеки, месяцев')).toHaveValue(180)
    expect(screen.getByLabelText('Годовая ставка, %')).toHaveValue(8.25)
    expect(screen.getByLabelText('Использовать льготный период')).toBeChecked()
    expect(
      screen.getByLabelText('Льготный период, месяцев'),
    ).toHaveValue(24)
    expect(screen.getByLabelText('Ставка льготного периода, %')).toHaveValue(5.25)
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
      expect(screen.getByLabelText('Дата первоначального взноса')).toHaveValue(
        '2026-01-15',
      )
    })
    const initialPaymentInput = screen.getByLabelText('Первоначальный взнос, %')
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

  it('saves and links the authoritative result from a customer flow', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(mortgageResult), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(savedCalculation), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)
    renderCalculator({
      initialRoute: '/?propertyId=3&propertyCost=5000000.00&customerId=12',
      session: authenticatedSession,
    })

    await user.click(screen.getByRole('button', { name: 'Рассчитать ипотеку' }))
    await user.click(
      await screen.findByRole('button', { name: 'Сохранить расчёт' }),
    )

    expect(
      await screen.findByRole('link', { name: 'Открыть карточку клиента' }),
    ).toHaveAttribute('href', '/customers/12')
    const saveRequest = fetchMock.mock.calls[1]
    expect(saveRequest[0]).toBe('/api/v1/mortgage/calculations/')
    expect(JSON.parse(saveRequest[1].body as string)).toEqual({
      propertyId: 3,
      customerId: 12,
      parameters: expect.objectContaining({
        propertyCost: '5000000.00',
        mortgageTermMonths: 360,
      }),
    })
  })
})
