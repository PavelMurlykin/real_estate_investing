import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type {
  DeveloperMortgageProgram,
  DeveloperMortgageProgramOptions,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { DeveloperMortgageProgramFormPage } from './DeveloperMortgageProgramFormPage'

const manager: Session = {
  isAuthenticated: true,
  user: { id: 1, displayName: 'Модератор', email: 'manager@example.com', agencyName: '' },
  capabilities: {
    manageCatalogs: true,
    syncExternalData: false,
    viewPrivateRecords: true,
    viewAllPrivateRecords: false,
  },
}
const emptyTruncation = {
  companyGroups: false,
  realEstateComplexes: false,
  banks: false,
  mortgagePrograms: false,
}
const baseOptions: DeveloperMortgageProgramOptions = {
  companyGroups: [{ id: 4, name: 'Группа Север' }],
  realEstateComplexes: [],
  banks: [{ id: 2, name: 'Тест Банк' }],
  mortgagePrograms: [{ id: 5, name: 'Семейная ипотека' }],
  truncated: emptyTruncation,
}
const groupedOptions: DeveloperMortgageProgramOptions = {
  ...baseOptions,
  realEstateComplexes: [{ id: 7, name: 'ЖК Речной (Север Девелопмент)' }],
}
const program: DeveloperMortgageProgram = {
  id: 9,
  companyGroupId: 4,
  companyGroupName: 'Группа Север',
  realEstateComplexId: 7,
  realEstateComplexName: 'ЖК Речной',
  complexDeveloperName: 'Север Девелопмент',
  bankId: 2,
  bankName: 'Тест Банк',
  mortgageProgramId: 5,
  mortgageProgramName: 'Семейная ипотека',
  priceIncreasePercent: '-1.25',
  gracePeriodMonths: 24,
  gracePeriodInterestRate: '0.10',
  minimumInitialPaymentPercent: '20.10',
  interestRate: '4.30',
  maximumLoanTermYears: 30,
  maximumLoanAmount: '12000000.00',
  rateDiscountPercent: '0.50',
  isActive: true,
  createdAt: '2026-01-10T10:00:00Z',
  updatedAt: '2026-01-11T10:00:00Z',
  detailUrl: '/developer-programs/9',
  legacyEditUrl: '/bank/developer-programs/9/edit/',
  legacyCatalogUrl: '/bank/developer-programs/',
}

function managerClient() {
  const client = createTestQueryClient()
  client.setQueryData(['session'], manager)
  client.setQueryData(['developer-mortgage-program-options', null], baseOptions)
  client.setQueryData(['developer-mortgage-program-options', 4], groupedOptions)
  return client
}

function renderCreate() {
  return renderWithProviders(
    <Routes>
      <Route path="/developer-programs/new" element={<DeveloperMortgageProgramFormPage />} />
      <Route path="/developer-programs/:developerProgramId" element={<h1>Программа сохранена</h1>} />
    </Routes>,
    { initialRoute: '/developer-programs/new', queryClient: managerClient() },
  )
}

describe('DeveloperMortgageProgramFormPage', () => {
  it('does not request protected form data for an anonymous visitor', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(
      <Routes>
        <Route path="/developer-programs/new" element={<DeveloperMortgageProgramFormPage />} />
      </Routes>,
      { initialRoute: '/developer-programs/new' },
    )

    expect(screen.getByRole('heading', {
      name: 'Войдите для управления программами',
    })).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('creates complete conditions with a group-scoped complex', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify(program),
      { status: 201, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderCreate()

    await user.selectOptions(screen.getByLabelText('Группа компаний *'), '4')
    await user.selectOptions(screen.getByLabelText('Жилой комплекс'), '7')
    await user.selectOptions(screen.getByLabelText('Банк *'), '2')
    await user.selectOptions(screen.getByLabelText('Ипотечная программа *'), '5')
    await user.type(screen.getByLabelText('Удорожание, %'), '-1.25')
    await user.type(screen.getByLabelText('Первоначальный взнос, %'), '20.1')
    await user.type(screen.getByLabelText('Годовая ставка, %'), '4.3')
    await user.type(screen.getByLabelText('Дисконт к ставке, п. п.'), '0.5')
    await user.type(screen.getByLabelText('Срок льготного периода, мес.'), '24')
    await user.type(screen.getByLabelText('Ставка льготного периода, %'), '0.1')
    await user.type(screen.getByLabelText('Максимальный срок, лет'), '30')
    await user.type(screen.getByLabelText('Максимальная сумма, ₽'), '12000000')
    await user.click(screen.getByRole('button', { name: 'Создать программу' }))

    expect(await screen.findByRole('heading', { name: 'Программа сохранена' }))
      .toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/developer-mortgage-programs/')
    const request = fetchMock.mock.calls[0][1] as RequestInit
    expect(request.method).toBe('POST')
    expect(JSON.parse(request.body as string)).toEqual({
      companyGroupId: 4,
      realEstateComplexId: 7,
      bankId: 2,
      mortgageProgramId: 5,
      priceIncreasePercent: '-1.25',
      gracePeriodMonths: 24,
      gracePeriodInterestRate: '0.1',
      minimumInitialPaymentPercent: '20.1',
      interestRate: '4.3',
      maximumLoanTermYears: 30,
      maximumLoanAmount: '12000000',
      rateDiscountPercent: '0.5',
      isActive: true,
    })
  })

  it('prefills and updates all editable conditions', async () => {
    const user = userEvent.setup()
    const client = managerClient()
    client.setQueryData(['developer-mortgage-program', 9], program)
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ ...program, interestRate: '4.10' }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(
      <Routes>
        <Route path="/developer-programs/:developerProgramId/edit" element={<DeveloperMortgageProgramFormPage />} />
        <Route path="/developer-programs/:developerProgramId" element={<h1>Программа сохранена</h1>} />
      </Routes>,
      { initialRoute: '/developer-programs/9/edit', queryClient: client },
    )

    expect(await screen.findByLabelText('Жилой комплекс')).toHaveValue('7')
    expect(screen.getByLabelText('Годовая ставка, %')).toHaveValue(4.3)
    expect(screen.getByRole('link', { name: 'Django-форма' }))
      .toHaveAttribute('href', '/bank/developer-programs/9/edit/')
    await user.clear(screen.getByLabelText('Годовая ставка, %'))
    await user.type(screen.getByLabelText('Годовая ставка, %'), '4.1')
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }))

    expect(await screen.findByRole('heading', { name: 'Программа сохранена' }))
      .toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/developer-mortgage-programs/9/')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('PATCH')
  })

  it('blocks invalid percentages before sending a request', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderCreate()
    await user.selectOptions(screen.getByLabelText('Группа компаний *'), '4')
    await user.selectOptions(screen.getByLabelText('Банк *'), '2')
    await user.selectOptions(screen.getByLabelText('Ипотечная программа *'), '5')
    await user.type(screen.getByLabelText('Годовая ставка, %'), '101')
    await user.click(screen.getByRole('button', { name: 'Создать программу' }))

    expect(screen.getByText('Введите число от 0 до 100.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
