import { chooseOption } from '@/test/chooseOption'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { BankListResponse, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { BankListPage } from './BankListPage'

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

const bankDirectory: BankListResponse = {
  page: 1,
  pageSize: 10,
  totalCount: 1,
  totalPages: 1,
  results: [
    {
      id: 7,
      name: 'Северный банк',
      logoUrl: 'https://example.com/bank.svg',
      programCount: 1,
      programs: [{
        id: 1, mortgageProgramId: 9, mortgageProgramName: 'Семейная ипотека',
        interestRate: '5.90', minimumInitialPaymentPercent: '20.10', maximumLoanTermYears: 30,
      }],
      minimumInterestRate: '5.90',
      isActive: true,
      updatedAt: '2026-01-11T10:00:00Z',
      detailUrl: '/banks/7',
      legacyDetailUrl: '/bank/banks/7/',
    },
  ],
}

function createDirectoryQueryClient(session?: Session) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['banks', ''], bankDirectory)
  if (session) queryClient.setQueryData(['session'], session)
  return queryClient
}

describe('BankListPage', () => {
  it('uploads the bank file and displays the result for administrators', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (path: string) => Response.json(path.endsWith('/import/')
      ? { created: 2, updated: 3, unchanged: 1 } : bankDirectory))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<BankListPage />, { queryClient: createDirectoryQueryClient({
      ...managerSession, capabilities: { ...managerSession.capabilities, syncExternalData: true },
    }) })
    await user.click(screen.getByText('Импорт банков из JSON'))
    const file = new File(['{}'], 'banks.json', { type: 'application/json' })
    await user.upload(screen.getByLabelText('Файл JSON'), file)
    await user.click(screen.getByRole('button', { name: 'Импортировать' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Создано 2, обновлено 3, без изменений 1.')
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/banks/import/', expect.objectContaining({
      method: 'POST', body: expect.any(FormData),
    }))
    expect(screen.queryByText('Импорт ипотечных программ из JSON')).not.toBeInTheDocument()
  })

  it('limits import to administrators', () => {
    renderWithProviders(<BankListPage />, { queryClient: createDirectoryQueryClient(managerSession) })
    expect(screen.queryByText('Импорт банков из JSON')).not.toBeInTheDocument()
  })

  it('shows bank terms when the disclosure is opened', async () => {
    const user = userEvent.setup()
    renderWithProviders(<BankListPage />, { queryClient: createDirectoryQueryClient() })
    const table = within(screen.getByRole('table'))
    await user.click(table.getByLabelText('Ипотечные программы — Северный банк'))
    expect(table.getByRole('link', { name: 'Семейная ипотека' })).toHaveAttribute('href', '/mortgage-programs/9')
    expect(table.getByText('от 5,9% · взнос от 20,1% · до 30 лет')).toBeVisible()
  })

  it('renders the public directory with React detail links', () => {
    renderWithProviders(<BankListPage />, {
      queryClient: createDirectoryQueryClient(),
    })

    expect(
      screen.getByRole('heading', { name: 'Банки и программы' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveAccessibleName('Список банков')
    expect(screen.getAllByText('Северный банк')).toHaveLength(2)
    expect(screen.getAllByText('от 5,9%')).toHaveLength(1)
    expect(
      screen.getAllByRole('link', { name: 'Северный банк' })[0],
    ).toHaveAttribute('href', '/banks/7')
    expect(screen.queryByRole('link', { name: 'Добавить банк' }))
      .not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Прежняя версия' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Найти' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Статус')).not.toBeInTheDocument()
  })

  it('combines live search with the program filter and resets both', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async () => Response.json(bankDirectory))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<BankListPage />, {
      initialRoute: '/banks?status=inactive',
      queryClient: createDirectoryQueryClient(),
    })

    const search = screen.getByRole('searchbox', { name: 'Поиск' })
    const scope = screen.getByRole('combobox', { name: 'Программы' })
    await user.type(search, 'Северный')
    await chooseOption(user, 'Программы', 'С программами')
    const parameters = new URLSearchParams({ q: 'Северный', scope: 'withPrograms' })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/banks/?${parameters}`,
      expect.objectContaining({ credentials: 'same-origin' }),
    ))

    await user.click(screen.getByRole('button', { name: 'Сбросить' }))
    expect(search).toHaveValue('')
    expect(scope).toHaveValue('')
  })

  it('shows React create and edit routes to catalog managers', () => {
    renderWithProviders(<BankListPage />, {
      queryClient: createDirectoryQueryClient(managerSession),
    })

    expect(screen.getByRole('link', { name: 'Добавить банк' }))
      .toHaveAttribute('href', '/banks/new')
    expect(screen.getByRole('link', { name: 'Редактировать: Северный банк' }))
      .toHaveAttribute('href', '/banks/7/edit')
  })

  it('explains a protected developer-program link on delete', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Банк используется.' }), {
          status: 409,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    renderWithProviders(<BankListPage />, {
      queryClient: createDirectoryQueryClient(managerSession),
    })

    await user.click(screen.getByRole('button', {
      name: 'Удалить: Северный банк',
    }))
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveAccessibleName('Удалить банк?')
    expect(within(dialog).getByRole('button', { name: 'Отмена' })).toHaveFocus()
    await user.click(within(dialog).getByRole('button', { name: 'Удалить' }))

    expect(await within(dialog).findByText(
      'Банк используется в программах застройщиков. Сначала переназначьте эти связи.',
    )).toBeInTheDocument()
  })
})
