import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  MortgageCalculationResponse,
  MortgageOptions,
  PropertyListResponse,
  SavedMortgageCalculationDetail,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'
import { mockMortgageCatalogs } from '@/test/mockMortgageCatalogs'
import { downloadFile } from '@/shared/lib/downloadFile'

import { MortgageCalculatorPage } from './MortgageCalculatorPage'

vi.mock('@/shared/lib/downloadFile', () => ({ downloadFile: vi.fn() }))

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
    regionId: 1, cityId: 1, districtId: 1, developerId: 1,
    realEstateComplexId: 1, buildingId: 1, layoutId: 1, decorationId: 1,
    district: 'Центральный',
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

function resultForMode(mode: 'market' | 'trench') {
  if (mode === 'market') return mortgageResult
  return {
    assumptions: { ...mortgageResult.assumptions, trenchCount: 1 },
    summary: { ...mortgageResult.summary, maximumMonthlyPayment: mortgageResult.summary.mainMonthlyPayment },
    schedule: mortgageResult.schedule,
    trenches: [{ number: 1, date: '2026-01-15', percent: '100.00', amount: '4000000.00',
      annualRate: '15.00', monthlyPayment: mortgageResult.summary.mainMonthlyPayment,
      paymentsCount: 360, remainingDebt: '0.00', overpayment: mortgageResult.summary.overpayment }],
  }
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
  properties = propertyList,
  developerOptions,
  initialCalculationType = 'market',
  options = mortgageOptions,
}: {
  initialRoute?: string
  savedSample?: SavedMortgageCalculationDetail
  session?: Session
  properties?: PropertyListResponse | null
  developerOptions?: MortgageOptions
  initialCalculationType?: 'market' | 'trench'
  options?: MortgageOptions
} = {}) {
  const queryClient = createTestQueryClient()
  mockMortgageCatalogs(properties?.results.length ? properties.results : propertyList.results)
  queryClient.setQueryData(['mortgage-developer-options', 1], options)
  properties?.results.forEach((property) => {
    if (property.developerId) queryClient.setQueryData(['mortgage-developer-options', property.developerId], options)
  })
  queryClient.setQueryData(['mortgage-options'], options)
  if (properties) {
    queryClient.setQueryData(
      ['properties', 'mortgage-options', ''],
      { pages: [properties], pageParams: [1] },
    )
  }
  if (session) queryClient.setQueryData(['session'], session)
  if (developerOptions) {
    queryClient.setQueryData(['mortgage-developer-options', 9], developerOptions)
  }
  if (savedSample) {
    queryClient.setQueryData(
      ['saved-mortgage-calculation', savedSample.id],
      savedSample,
    )
  }
  return renderWithProviders(<MortgageCalculatorPage initialCalculationType={initialCalculationType} />, {
    initialRoute,
    queryClient,
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('MortgageCalculatorPage', () => {
  it.each(['market', 'trench'] as const)('keeps one visible form and permits a quick %s calculation with partial property details', async (mode) => {
    const user = userEvent.setup()
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json(resultForMode(mode)))
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderCalculator({ session: authenticatedSession, initialCalculationType: mode })
    expect(container.querySelectorAll('form')).toHaveLength(1)
    expect(screen.queryByRole('button', { name: 'Заполнить объект вручную' })).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Город' })).toBeVisible()
    expect(screen.getByLabelText('Номер квартиры')).not.toHaveAttribute('readonly')
    await user.type(screen.getByLabelText('Номер квартиры'), 'PARTIAL-42')
    await user.click(screen.getByRole('button', {
      name: mode === 'market' ? 'Рассчитать ипотеку' : 'Рассчитать траншевую ипотеку',
    }))
    expect(await screen.findByRole('button', { name: 'Сохранить расчёт' })).toBeDisabled()
    const request = fetchMock.mock.calls.find(([path]) => String(path).endsWith('/calculate/'))
    expect(JSON.parse(request?.[1]?.body as string)).not.toHaveProperty('manualProperty')
    expect(screen.getByLabelText('Номер квартиры')).toHaveValue('PARTIAL-42')
  })

  it.each(['market', 'trench'] as const)('detaches the old property and saves edited %s fields as a new snapshot', async (mode) => {
    const user = userEvent.setup()
    const response = resultForMode(mode)
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (path) => Response.json(
      String(path).endsWith('/calculate/') ? response : { ...savedCalculation, calculation: response },
      { status: String(path).endsWith('/calculate/') ? 200 : 201 },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderCalculator({ initialRoute: '/?propertyId=3', session: authenticatedSession, initialCalculationType: mode })
    const calculate = screen.getByRole('button', {
      name: mode === 'market' ? 'Рассчитать ипотеку' : 'Рассчитать траншевую ипотеку',
    })
    await user.click(calculate)
    expect(await screen.findByRole('button', { name: 'Сохранить расчёт' })).toBeEnabled()
    await user.clear(screen.getByLabelText('Номер квартиры'))
    await user.type(screen.getByLabelText('Номер квартиры'), 'NEW-42')
    expect(screen.getByRole('combobox', { name: 'Объект недвижимости' })).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Сохранить расчёт' })).toBeDisabled()
    await user.click(calculate)
    await user.click(await screen.findByRole('button', { name: 'Сохранить расчёт' }))
    const saved = fetchMock.mock.calls.find(([path]) => String(path).endsWith('/calculations/'))
    const payload = JSON.parse(saved?.[1]?.body as string)
    expect(payload).not.toHaveProperty('propertyId')
    expect(payload.parameters.manualProperty).toMatchObject({
      cityId: 1, buildingId: 1, apartmentNumber: 'NEW-42', area: '52.40',
    })
  })

  it.each(['market', 'trench'] as const)('searches and loads properties in one keyboard-accessible control in %s mode', async (mode) => {
    const user = userEvent.setup()
    const nextProperty = {
      ...propertyList.results[0], id: 4, apartmentNumber: '43',
      realEstateComplex: 'Другой ЖК', propertyCost: '5432100.67',
    }
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (path) => {
      const parameters = new URL(String(path), 'http://localhost').searchParams
      return new Response(JSON.stringify({
        ...propertyList,
        page: parameters.has('search') ? 1 : 2,
        totalPages: parameters.has('search') ? 1 : 2,
        results: [nextProperty],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderCalculator({
      initialCalculationType: mode, session: authenticatedSession,
      properties: { ...propertyList, totalPages: 2, totalCount: 101 },
    })
    expect(screen.queryByRole('link', { name: 'Django-версия' })).not.toBeInTheDocument()
    expect(screen.queryByRole('complementary', { name: 'Справочная информация' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Поиск объекта')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'История расчётов' })).toHaveAttribute(
      'href', mode === 'market' ? '/mortgage/calculations' : '/mortgage/trench/calculations',
    )
    const control = screen.getByRole('combobox', { name: 'Объект недвижимости' })
    await user.click(control)
    const list = screen.getByRole('listbox', { name: 'Варианты: Объект недвижимости' })
    fireEvent.scroll(list)
    expect(await screen.findByRole('option', { name: /Другой ЖК.*кв\. 43$/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Зелёный квартал.*кв\. 42$/ })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([path]) => String(path).includes('page=2'))).toBe(true)
    await user.type(control, 'Другой')
    await waitFor(() => expect(control).not.toHaveAttribute('aria-busy', 'true'))
    expect(await screen.findByRole('option', { name: /Другой ЖК.*кв\. 43$/ })).toBeInTheDocument()
    await user.keyboard('{Enter}')
    expect(control).toHaveValue('Казань, Другой ЖК, корпус 2, кв. 43')
    expect(screen.getByLabelText('Базовая стоимость, ₽')).toHaveValue(5432100.67)
    expect(screen.getByLabelText('Номер квартиры')).toHaveValue('43')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([path]) => String(path).includes('search='))).toBe(true)
    expect(fetchMock.mock.calls.every(([, options]) => !options?.method || options.method === 'GET')).toBe(true)
  })

  it('retries the property list with the keyboard after a loading error', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValue(new Response(JSON.stringify(propertyList), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      })))
    renderCalculator({ properties: null, session: authenticatedSession })
    await user.click(screen.getByRole('combobox', { name: 'Объект недвижимости' }))
    const retry = await screen.findByRole('button', { name: 'Повторить загрузку справочника' })
    await user.tab()
    expect(retry).toHaveFocus()
    await user.keyboard('{Enter}')
    await user.click(await screen.findByRole('option', { name: /кв\. 42$/ }))
    expect(screen.getByLabelText('Номер квартиры')).toHaveValue('42')
  })

  it.each(['market', 'trench'] as const)('matches Django integer year fields in %s mode', async (mode) => {
    const user = userEvent.setup()
    renderCalculator({ initialCalculationType: mode })
    const years = screen.getByLabelText('Срок ипотеки, лет')
    const months = screen.getByLabelText('Срок ипотеки, месяцев')
    fireEvent.change(years, { target: { value: '12.5' } })
    expect(months).toHaveValue(144)
    fireEvent.change(months, { target: { value: '25' } })
    expect(years).toHaveValue(2)
    if (mode === 'market') {
      await user.click(screen.getByLabelText('Использовать льготный период'))
      fireEvent.change(screen.getByLabelText('Льготный период, лет'), { target: { value: '1.5' } })
      expect(screen.getByLabelText('Льготный период, месяцев')).toHaveValue(12)
      fireEvent.change(screen.getByLabelText('Льготный период, месяцев'), { target: { value: '6' } })
      expect(screen.getByLabelText('Льготный период, лет')).toHaveValue(0)
    }
  })

  it('starts a quick tranche calculation with one residual tranche and a populated date', () => {
    renderCalculator({ initialCalculationType: 'trench' })
    expect(screen.getByLabelText('Количество траншей')).toHaveValue('1')
    expect(screen.getAllByLabelText('Дата транша')).toHaveLength(1)
    expect(screen.getByLabelText('Дата транша')).toHaveValue(mortgageOptions.defaultInitialPaymentDate)
    expect(screen.getByLabelText('Сумма транша, %')).toHaveAttribute('readonly')
    expect(screen.getByLabelText('Сумма транша, ₽')).toHaveAttribute('readonly')
  })

  it('uses the selected property on the first calculation even when its catalog data arrives late', async () => {
    const user = userEvent.setup()
    let resolveCatalog: (response: Response) => void = () => undefined
    const catalog = new Promise<Response>((resolve) => { resolveCatalog = resolve })
    const fetchMock = vi.fn((path: string) => {
      if (path.startsWith('/api/v1/properties/?')) return catalog
      if (path === '/api/v1/properties/3/') return new Promise<Response>(() => {})
      return Promise.resolve(new Response(JSON.stringify(mortgageResult), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderCalculator({ initialRoute: '/?propertyId=3', properties: null, session: authenticatedSession })

    const calculate = screen.getByRole('button', { name: 'Рассчитать ипотеку' })
    expect(calculate).toBeDisabled()
    expect(screen.getByText('Загружаем данные объекта…')).toBeInTheDocument()
    fireEvent.submit(calculate.closest('form') as HTMLFormElement)
    expect(fetchMock.mock.calls.some(([path]) => path === '/api/v1/mortgage/calculate/')).toBe(false)

    resolveCatalog(new Response(JSON.stringify({
      ...propertyList,
      results: [{ ...propertyList.results[0], propertyCost: '6300000.00' }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    await waitFor(() => expect(calculate).toBeEnabled())
    await user.click(calculate)
    const save = await screen.findByRole('button', { name: 'Сохранить расчёт' })
    expect(save).toBeEnabled()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/mortgage/calculate/', expect.objectContaining({
      body: expect.stringContaining('"propertyCost":"6300000.00"'),
    }))
  })

  it('can retry an unavailable property or edit the visible property fields', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(() => Promise.resolve(new Response(null, { status: 503 })))
    vi.stubGlobal('fetch', fetchMock)
    renderCalculator({
      initialRoute: '/?propertyId=3',
      properties: { ...propertyList, totalCount: 0, results: [] },
      session: authenticatedSession,
    })

    const calculate = screen.getByRole('button', { name: 'Рассчитать ипотеку' })
    const retry = await screen.findByRole('button', { name: 'Повторить загрузку объекта' })
    expect(calculate).toBeDisabled()
    await user.click(retry)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    await screen.findByRole('button', { name: 'Повторить загрузку объекта' })
    await user.type(screen.getByLabelText('Номер квартиры'), 'NEW')
    expect(calculate).toBeEnabled()
  })

  it('submits manual object identifiers and allows a moderator to save the scenario', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockImplementation(async (path: string) => {
      if (path.includes('/catalog-options/')) {
        const dictionary = path.split('/catalog-options/')[1].split('/')[0]
        const label = dictionary === 'complexes' ? 'Ручной ЖК' : dictionary
        const option = { id: 1, label, regionId: 1, cityId: 1, districtId: 1, developerId: 1, realEstateComplexId: 1 }
        return new Response(JSON.stringify({ results: [option], selected: [option], totalCount: 1, page: 1, nextPage: null }),
          { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      const response = path.includes('/options/') ? { ...mortgageOptions, developerPrograms: [] }
        : path.endsWith('/calculate/') ? mortgageResult : savedCalculation
      return new Response(JSON.stringify(response), { status: path.endsWith('/calculations/') ? 201 : 200, headers: { 'Content-Type': 'application/json' } })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderCalculator({ session: { ...authenticatedSession, capabilities: { ...authenticatedSession.capabilities, manageCatalogs: true } } })
    for (const [label, choice] of [
      ['Жилой комплекс', 'Зелёный квартал'], ['Корпус', '2'],
      ['Планировка', 'Евродвушка'], ['Отделка', 'Чистовая'],
    ]) {
      await user.click(screen.getByRole('combobox', { name: label }))
      await user.click(await screen.findByRole('option', { name: choice }))
    }
    await user.type(screen.getByLabelText('Номер квартиры'), 'NEW-42')
    await user.type(screen.getByLabelText('Площадь, м²'), '51.25')
    await user.type(screen.getByLabelText('Этаж'), '9')
    await user.click(screen.getByRole('button', { name: 'Рассчитать ипотеку' }))
    await user.click(await screen.findByRole('button', { name: 'Сохранить расчёт' }))
    const calculation = fetchMock.mock.calls.find(([path]) => path === '/api/v1/mortgage/calculate/')
    expect(JSON.parse(calculation?.[1].body as string).manualProperty).toEqual({
      cityId: 1, districtId: 1, developerId: 1, realEstateComplexId: 1, buildingId: 1,
      apartmentNumber: 'NEW-42', area: '51.25', floor: 9, layoutId: 1, decorationId: 1,
    })
    const saved = fetchMock.mock.calls.find(([path]) => path === '/api/v1/mortgage/calculations/')
    expect(JSON.parse(saved?.[1].body as string)).not.toHaveProperty('propertyId')
  })

  it('exports an anonymous scenario without selecting or saving a property', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockImplementation(async (path: string) => (
      path.includes('/export/')
        ? new Response('workbook', { status: 200, headers: { 'Content-Type': 'application/octet-stream', 'Content-Disposition': 'attachment; filename="scenario.xlsx"' } })
        : new Response(JSON.stringify(mortgageResult), { status: 200, headers: { 'Content-Type': 'application/json' } })
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderCalculator()
    await user.click(screen.getByRole('button', { name: 'Рассчитать ипотеку' }))
    await user.click(await screen.findByRole('button', { name: 'Excel' }))
    await waitFor(() => expect(downloadFile).toHaveBeenCalledWith(expect.objectContaining({ filename: 'scenario.xlsx' })))
    const exported = fetchMock.mock.calls.find(([path]) => path === '/api/v1/mortgage/export/excel/')
    expect(JSON.parse(exported?.[1].body as string)).toEqual({ parameters: expect.objectContaining({ propertyCost: '5000000' }) })
    expect(fetchMock.mock.calls.some(([path]) => path === '/api/v1/mortgage/calculations/')).toBe(false)
  })

  it.each(['market', 'trench'] as const)('applies complex conditions and restores group defaults in %s mode', async (mode) => {
    const user = userEvent.setup()
    const groupProgram = {
      id: 500, companyGroupId: 1, companyGroupName: 'Группа',
      realEstateComplexId: null, realEstateComplexName: null, complexDeveloperName: null,
      bankId: 1, bankName: 'Надёжный банк', mortgageProgramId: 20,
      mortgageProgramName: 'Семейная ипотека', priceIncreasePercent: '-2.50',
      gracePeriodMonths: null, gracePeriodInterestRate: null,
      minimumInitialPaymentPercent: '21', interestRate: '5',
      maximumLoanTermYears: 20, maximumLoanAmount: null, rateDiscountPercent: null,
      isActive: true, createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z',
      detailUrl: '', legacyEditUrl: '', legacyCatalogUrl: '',
    }
    renderCalculator({
      initialRoute: '/?propertyId=3', initialCalculationType: mode,
      properties: {
        ...propertyList, totalCount: 2,
        results: [
          { ...propertyList.results[0], developerId: 9, realEstateComplexId: 30, regionId: 2, district: 'Центральный' },
          { ...propertyList.results[0], id: 4, apartmentNumber: '43', developerId: 9, realEstateComplexId: 31, regionId: 2 },
        ],
      },
      developerOptions: {
        ...mortgageOptions,
        developerPrograms: [groupProgram, {
          ...groupProgram, id: 501, realEstateComplexId: 30, realEstateComplexName: 'Зелёный квартал',
          priceIncreasePercent: '8', interestRate: '3', minimumInitialPaymentPercent: '25',
          maximumLoanTermYears: 25, gracePeriodMonths: 24, gracePeriodInterestRate: '1',
        }],
      },
    })
    await user.selectOptions(screen.getByLabelText('Банк'), '1')
    await user.selectOptions(screen.getByLabelText('Ипотечная программа'), '10')
    expect(screen.getAllByLabelText('Годовая ставка, %')[0]).toHaveValue(3)
    expect(screen.getByLabelText('Удорожание, %')).toHaveValue(8)
    expect(screen.getByLabelText('Первоначальный взнос, %')).toHaveValue(25)
    expect(screen.getByLabelText('Срок ипотеки, месяцев')).toHaveValue(300)
    if (mode === 'market') {
      expect(screen.getByLabelText('Льготный период, месяцев')).toHaveValue(24)
      expect(screen.getByLabelText('Ставка льготного периода, %')).toHaveValue(1)
    } else {
      expect(screen.getAllByLabelText('Годовая ставка, %').every((input) => (input as HTMLInputElement).value === '3')).toBe(true)
    }
    expect(screen.getByLabelText('Район')).toHaveValue('Центральный')
    const fetchMock = vi.fn().mockImplementation(() => new Promise(() => {}))
    vi.stubGlobal('fetch', fetchMock)
    await user.type(screen.getByRole('combobox', { name: 'Объект недвижимости' }), 'Другой ЖК')
    await waitFor(() => expect(fetchMock.mock.calls.some(([path]) => String(path).includes('search='))).toBe(true))
    expect(screen.getAllByLabelText('Годовая ставка, %')[0]).toHaveValue(3)
    expect(screen.getByLabelText('Удорожание, %')).toHaveValue(8)
    await user.clear(screen.getByRole('combobox', { name: 'Объект недвижимости' }))
    await waitFor(() => expect(screen.getByLabelText('Объект недвижимости')).toBeEnabled())
    await user.click(screen.getByRole('combobox', { name: 'Объект недвижимости' }))
    await user.click(await screen.findByRole('option', { name: /кв\. 43$/ }))
    expect(screen.getAllByLabelText('Годовая ставка, %')[0]).toHaveValue(5)
    expect(screen.getByLabelText('Скидка, %')).toHaveValue(2.5)
    expect(screen.getByLabelText('Первоначальный взнос, %')).toHaveValue(21)
    if (mode === 'market') expect(screen.getByLabelText('Использовать льготный период')).not.toBeChecked()
    await user.selectOptions(screen.getByLabelText('Ипотечная программа'), '')
    expect(screen.getByLabelText('Скидка, %')).toHaveValue(0)
    expect(screen.getAllByLabelText('Годовая ставка, %')[0]).toHaveValue(6)
    expect(screen.getByLabelText('Первоначальный взнос, %')).toHaveValue(25)
    expect(screen.getByLabelText('Срок ипотеки, месяцев')).toHaveValue(240)
  })

  it('uses the regional limit and explains additional down payment and combined rate', async () => {
    const user = userEvent.setup()
    renderCalculator({
      initialRoute: '/?propertyId=3',
      properties: { ...propertyList, results: [{ ...propertyList.results[0], regionId: 2 }] },
      options: {
        ...mortgageOptions,
        programs: [{ ...mortgageOptions.programs[0], regionalCreditLimits: [{ regionId: 2, creditLimit: '2000000' }] }],
      },
    })
    await user.selectOptions(screen.getByLabelText('Банк'), '1')
    await user.selectOptions(screen.getByLabelText('Ипотечная программа'), '10')
    expect(screen.getByRole('heading', { name: 'Сумма кредита превышает лимит программы' })).toBeInTheDocument()
    expect(screen.getByText(/Лимит кредита:/)).toHaveTextContent(/2\s000\s000/)
    expect(screen.getByText(/Необходимый взнос:/)).toHaveTextContent(/3\s000\s000/)
    expect(screen.getByText(/Дополнительно:/)).toHaveTextContent(/1\s750\s000/)
    expect(screen.getByText(/Итоговая ставка:/)).toHaveTextContent('11,6%')
  })

  it('requires recalculation after changing the property and saves the new snapshot', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockImplementation(async (url: string) => (
      new Response(JSON.stringify(url.endsWith('/calculate/')
        ? mortgageResult : savedCalculation), {
        status: url.endsWith('/calculate/') ? 200 : 201,
        headers: { 'Content-Type': 'application/json' },
      })
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderCalculator({
      initialRoute: '/?propertyId=3',
      session: authenticatedSession,
      properties: {
        ...propertyList,
        totalCount: 2,
        results: [propertyList.results[0], {
          ...propertyList.results[0], id: 4,
          apartmentNumber: '43', propertyCost: '5432100.67',
        }],
      },
    })
    await user.click(screen.getByRole('button', { name: 'Рассчитать ипотеку' }))
    expect(await screen.findByRole('button', { name: 'Сохранить расчёт' })).toBeEnabled()
    await user.click(screen.getByRole('combobox', { name: 'Объект недвижимости' }))
    await user.click(await screen.findByRole('option', { name: /кв\. 43$/ }))
    expect(screen.getByRole('button', { name: 'Сохранить расчёт' })).toBeDisabled()
    expect(screen.getByText('Данные изменены. Повторите расчёт перед сохранением.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Рассчитать ипотеку' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Сохранить расчёт' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Сохранить расчёт' }))
    const saveRequest = fetchMock.mock.calls.find(([url]) => url === '/api/v1/mortgage/calculations/')
    expect(JSON.parse(saveRequest?.[1].body as string)).toMatchObject({
      propertyId: 4,
      parameters: { propertyCost: '5432100.67' },
    })
  })

  it('marks the calculated result outdated after editing a financial input', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mortgageResult), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }),
    ))
    renderCalculator({ initialRoute: '/?propertyId=3', session: authenticatedSession })
    await user.click(screen.getByRole('button', { name: 'Рассчитать ипотеку' }))
    expect(await screen.findByRole('button', { name: 'Сохранить расчёт' })).toBeEnabled()
    await user.clear(screen.getByLabelText('Годовая ставка, %'))
    await user.type(screen.getByLabelText('Годовая ставка, %'), '10')
    expect(screen.getByRole('button', { name: 'Сохранить расчёт' })).toBeDisabled()
  })

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
        (_, element) => element?.textContent?.replace(/\s/g, '') === '50577,51₽',
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
    await user.click(screen.getByRole('combobox', { name: 'Объект недвижимости' }))
    await user.click(await screen.findByRole('option', { name: /кв\. 42$/ }))

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
