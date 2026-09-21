import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  MortgageOptions,
  SavedTrenchMortgageCalculationDetail,
  Session,
  TrenchMortgageCalculationResponse,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { TrenchMortgageCalculatorPage } from './TrenchMortgageCalculatorPage'

const mortgageOptions: MortgageOptions = {
  defaultInitialPaymentDate: '2026-01-15',
  keyRate: '16.00',
  banks: [],
  programs: [],
}

const propertyList = {
  page: 1,
  pageSize: 100,
  totalCount: 1,
  totalPages: 1,
  results: [{
    id: 42,
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
    detailUrl: '/property/42/',
  }],
}

const authenticatedSession: Session = {
  isAuthenticated: true,
  user: {
    id: 7,
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

const calculationResponse: TrenchMortgageCalculationResponse = {
  assumptions: {
    basePropertyCost: '5000000.00',
    priceAdjustmentType: 'discount',
    priceAdjustmentPercent: '0.00',
    priceAdjustmentRubles: '0.00',
    finalPropertyCost: '5000000.00',
    initialPaymentPercent: '20.00',
    initialPaymentRubles: '1000000.00',
    initialPaymentDate: '2026-01-15',
    mortgageTermMonths: 24,
    annualRate: '12.00',
    trenchCount: 2,
  },
  summary: {
    loanAmount: '4000000.00',
    maximumMonthlyPayment: '190000.00',
    overpayment: '430000.00',
    totalPayments: '4430000.00',
    paymentsCount: 24,
    mortgageEndDate: '2028-01-15',
  },
  trenches: [
    {
      number: 1,
      date: '2026-01-15',
      percent: '50.00',
      amount: '2000000.00',
      annualRate: '12.00',
      monthlyPayment: '95000.00',
      paymentsCount: 6,
      remainingDebt: '2000000.00',
      overpayment: '180000.00',
    },
    {
      number: 2,
      date: '2026-07-15',
      percent: '50.00',
      amount: '2000000.00',
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
      paymentAmount: '95000.00',
      interestAmount: '20000.00',
      principalAmount: '75000.00',
      remainingDebt: '1925000.00',
    },
    {
      paymentNumber: 2,
      paymentDate: '2026-02-15',
      paymentAmount: '95000.00',
      interestAmount: '19250.00',
      principalAmount: '75750.00',
      remainingDebt: '1849250.00',
    },
  ],
}

const savedSample: SavedTrenchMortgageCalculationDetail = {
  id: 17,
  createdAt: '2026-09-10T10:30:00+03:00',
  property: {
    id: 42,
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
    detailUrl: '/property/42/',
  },
  legacyDetailUrl: '/mortgage/trench-calculations/17/',
  calculation: calculationResponse,
}

function renderPage({
  authenticated = false,
  route = '/mortgage/trench',
}: {
  authenticated?: boolean
  route?: string
} = {}) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['mortgage-options'], mortgageOptions)
  queryClient.setQueryData(
    ['properties', 'pageSize=100&ordering=realEstateComplex'],
    propertyList,
  )
  if (authenticated) {
    queryClient.setQueryData(['session'], authenticatedSession)
  }
  if (authenticated && route.includes('sample=17')) {
    queryClient.setQueryData(
      ['saved-trench-mortgage-calculation', 17],
      savedSample,
    )
  }
  return renderWithProviders(<TrenchMortgageCalculatorPage />, {
    initialRoute: route,
    queryClient,
  })
}

async function fillTrenchDates(user: ReturnType<typeof userEvent.setup>) {
  const dateInputs = screen.getAllByLabelText('Дата транша')
  await user.clear(dateInputs[0])
  await user.type(dateInputs[0], '2026-01-15')
  await user.type(dateInputs[1], '2026-07-15')
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('TrenchMortgageCalculatorPage', () => {
  it('changes the bounded tranche editor and keeps the last tranche automatic', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(screen.getAllByLabelText('Дата транша')).toHaveLength(2)
    expect(screen.getAllByRole('spinbutton', { name: 'Сумма транша, %' })[1]).toHaveAttribute(
      'readonly',
    )

    await user.selectOptions(
      screen.getByLabelText('Количество траншей'),
      '3',
    )

    expect(screen.getAllByLabelText('Дата транша')).toHaveLength(3)
    expect(screen.getAllByRole('spinbutton', { name: 'Сумма транша, %' })).toHaveLength(3)
    expect(screen.getAllByRole('spinbutton', { name: 'Сумма транша, %' })[2]).toHaveAttribute(
      'readonly',
    )
  })

  it('submits normalized rows and renders the server result', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(calculationResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderPage()
    await fillTrenchDates(user)

    await user.click(screen.getByRole('button', {
      name: 'Рассчитать траншевую ипотеку',
    }))

    expect(await screen.findByRole('heading', {
      name: 'Параметры траншевого кредита',
    })).toBeInTheDocument()
    expect(screen.getByText('4 000 000 ₽')).toBeInTheDocument()
    expect(screen.getByRole('table', {
      name: 'Рассчитанные параметры траншей',
    })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const requestOptions = fetchMock.mock.calls[0][1] as RequestInit
    const requestPayload = JSON.parse(requestOptions.body as string)
    expect(requestPayload.trenches).toHaveLength(2)
    expect(requestPayload.trenches[0]).toMatchObject({
      amountUnit: 'percent',
      amountValue: '50',
      date: '2026-01-15',
    })
    expect(requestPayload.trenches[1].amountValue).toBeNull()
  })

  it('shows nested server errors beside the affected tranche field', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(JSON.stringify({
          trenches: {
            0: { amountValue: ['Сумма транша превышает остаток кредита.'] },
          },
        }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    renderPage()
    await fillTrenchDates(user)

    await user.click(screen.getByRole('button', {
      name: 'Рассчитать траншевую ипотеку',
    }))

    expect(await screen.findByText(
      'Сумма транша превышает остаток кредита.',
    )).toBeInTheDocument()
    expect(screen.getAllByRole('spinbutton', { name: 'Сумма транша, ₽' })[0]).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('saves and links an authenticated result without duplicate writes', async () => {
    const user = userEvent.setup()
    let resolveSaveRequest: ((response: Response) => void) | undefined
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(calculationResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockImplementationOnce(
        () => new Promise<Response>((resolve) => {
          resolveSaveRequest = resolve
        }),
      )
    vi.stubGlobal('fetch', fetchMock)
    renderPage({
      authenticated: true,
      route: '/mortgage/trench?propertyId=42&propertyCost=5000000.00&customerId=12',
    })
    await fillTrenchDates(user)
    await user.click(screen.getByRole('button', {
      name: 'Рассчитать траншевую ипотеку',
    }))
    await screen.findByRole('heading', {
      name: 'Сохранить этот сценарий',
    })

    await user.click(screen.getByRole('button', { name: 'Сохранить расчёт' }))
    expect(screen.getByRole('button', { name: 'Сохраняем…' })).toBeDisabled()
    resolveSaveRequest?.(
      new Response(JSON.stringify({
        id: 17,
        legacyDetailUrl: '/mortgage/trench-calculations/17/',
        calculation: calculationResponse,
      }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    expect(await screen.findByRole('link', {
      name: 'Открыть карточку клиента',
    })).toHaveAttribute('href', '/customers/12')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const saveRequestOptions = fetchMock.mock.calls[1][1] as RequestInit
    expect(JSON.parse(saveRequestOptions.body as string)).toMatchObject({
      propertyId: 42,
      customerId: 12,
    })
  })

  it('loads a saved owner scenario into the form as a new sample', async () => {
    renderPage({
      authenticated: true,
      route: '/mortgage/trench?sample=17',
    })

    expect(await screen.findByLabelText('Первоначальный взнос, %')).toHaveValue(20)
    expect(screen.getAllByLabelText('Дата транша')[0]).toHaveValue(
      '2026-01-15',
    )
    expect(screen.getAllByLabelText('Дата транша')[1]).toHaveValue(
      '2026-07-15',
    )
    expect(screen.getAllByLabelText('Годовая ставка, %')[2]).toHaveValue(10)
  })
})
