import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { BankDetail, BankOptions, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { BankFormPage } from './BankFormPage'

const managerSession: Session = {
  isAuthenticated: true,
  user: {
    id: 1,
    displayName: 'Модератор',
    email: 'moderator@example.com',
    agencyName: '',
  },
  capabilities: {
    manageCatalogs: true,
    syncExternalData: false,
    viewPrivateRecords: true,
    viewAllPrivateRecords: false,
  },
}

const options: BankOptions = {
  mortgagePrograms: [
    { id: 3, name: 'Семейная ипотека' },
    { id: 4, name: 'Рыночная ипотека' },
  ],
  truncated: false,
}

const bank: BankDetail = {
  id: 7,
  name: 'Северный банк',
  logoUrl: 'https://example.com/bank.svg',
  isActive: true,
  createdAt: '2026-01-10T10:00:00Z',
  updatedAt: '2026-01-11T10:00:00Z',
  programs: [
    {
      id: 12,
      mortgageProgramId: 3,
      mortgageProgramName: 'Семейная ипотека',
      interestRate: '5.90',
      minimumInitialPaymentPercent: '20.10',
      maximumLoanTermYears: 30,
    },
  ],
  legacyDetailUrl: '/bank/banks/7/',
  legacyEditUrl: '/bank/banks/7/edit/',
  legacyCatalogUrl: '/bank/?model=bank',
}

function createManagerQueryClient() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['session'], managerSession)
  queryClient.setQueryData(['bank-options'], options)
  return queryClient
}

function renderCreateForm() {
  return renderWithProviders(
    <Routes>
      <Route path="/banks/new" element={<BankFormPage />} />
      <Route path="/banks/:bankId" element={<h1>Банк сохранён</h1>} />
    </Routes>,
    {
      initialRoute: '/banks/new',
      queryClient: createManagerQueryClient(),
    },
  )
}

describe('BankFormPage', () => {
  it('does not request form data for anonymous visitors', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(
      <Routes>
        <Route path="/banks/new" element={<BankFormPage />} />
      </Routes>,
      { initialRoute: '/banks/new' },
    )

    expect(screen.getByRole('heading', {
      name: 'Войдите для управления банками',
    })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Войти' })).toHaveAttribute(
      'href',
      '/app/login?next=%2Fapp%2Fbanks%2Fnew',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('creates a bank with its nested mortgage program conditions', async () => {
    const user = userEvent.setup()
    const createdBank = { ...bank, id: 10, name: 'Новый банк' }
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(createdBank), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderCreateForm()

    await user.type(screen.getByLabelText('Название *'), '  Новый банк  ')
    await user.type(
      screen.getByLabelText(/^URL логотипа/),
      'https://example.com/new.svg',
    )
    await user.click(screen.getByRole('button', { name: 'Добавить программу' }))
    await user.selectOptions(
      screen.getByLabelText('Ипотечная программа *'),
      '3',
    )
    await user.type(screen.getByLabelText('Ставка, % *'), '5.9')
    await user.type(screen.getByLabelText('Первый взнос, % *'), '20.1')
    await user.type(screen.getByLabelText('Максимальный срок, лет'), '30')
    await user.click(screen.getByRole('button', { name: 'Создать банк' }))

    expect(await screen.findByRole('heading', { name: 'Банк сохранён' }))
      .toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/banks/')
    const requestOptions = fetchMock.mock.calls[0][1] as RequestInit
    expect(requestOptions.method).toBe('POST')
    expect(JSON.parse(requestOptions.body as string)).toEqual({
      name: 'Новый банк',
      logoUrl: 'https://example.com/new.svg',
      isActive: true,
      programs: [
        {
          mortgageProgramId: 3,
          interestRate: '5.9',
          minimumInitialPaymentPercent: '20.1',
          maximumLoanTermYears: 30,
        },
      ],
    })
  })

  it('prefills and replaces existing bank conditions on update', async () => {
    const user = userEvent.setup()
    const queryClient = createManagerQueryClient()
    queryClient.setQueryData(['bank', 7], bank)
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        ...bank,
        name: 'Северо-Западный банк',
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(
      <Routes>
        <Route path="/banks/:bankId/edit" element={<BankFormPage />} />
        <Route path="/banks/:bankId" element={<h1>Банк сохранён</h1>} />
      </Routes>,
      { initialRoute: '/banks/7/edit', queryClient },
    )

    const nameInput = await screen.findByLabelText('Название *')
    expect(nameInput).toHaveValue('Северный банк')
    expect(screen.getByLabelText('Ипотечная программа *')).toHaveValue('3')
    expect(screen.getByLabelText('Ставка, % *')).toHaveValue(5.9)
    expect(screen.getByRole('link', { name: 'Django-форма' })).toHaveAttribute(
      'href',
      '/bank/banks/7/edit/',
    )
    await user.clear(nameInput)
    await user.type(nameInput, 'Северо-Западный банк')
    await user.click(screen.getByRole('button', {
      name: 'Сохранить изменения',
    }))

    expect(await screen.findByRole('heading', { name: 'Банк сохранён' }))
      .toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/banks/7/')
    const requestOptions = fetchMock.mock.calls[0][1] as RequestInit
    expect(requestOptions.method).toBe('PATCH')
    expect(JSON.parse(requestOptions.body as string).programs).toHaveLength(1)
  })

  it('blocks duplicate mortgage program rows before an API request', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderCreateForm()

    await user.type(screen.getByLabelText('Название *'), 'Новый банк')
    await user.click(screen.getByRole('button', { name: 'Добавить программу' }))
    await user.click(screen.getByRole('button', { name: 'Добавить программу' }))
    const programSelects = screen.getAllByLabelText('Ипотечная программа *')
    const rateInputs = screen.getAllByLabelText('Ставка, % *')
    const paymentInputs = screen.getAllByLabelText('Первый взнос, % *')
    for (let index = 0; index < 2; index += 1) {
      await user.selectOptions(programSelects[index], '3')
      await user.type(rateInputs[index], '6')
      await user.type(paymentInputs[index], '20')
    }
    await user.click(screen.getByRole('button', { name: 'Создать банк' }))

    expect(screen.getByText('Эта программа уже добавлена.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
