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
      programCount: 2,
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
  it.each([true, false])('exposes administrator sync mode %s and its warnings', async (updateBankRegistry) => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockImplementation(async (path: string) => new Response(JSON.stringify(path.endsWith('/sync/') ? {
      created: 2, updated: 3, processed: 5, banksProcessed: 4, offersProcessed: 6,
      referenceProgramsProcessed: 12, referenceProgramsCreated: 1, referenceProgramAliasesCreated: 2,
      googleSheetOffersProcessed: 3, skipped: 1, warnings: ['Источник временно недоступен'],
      updateBankRegistry, synchronizedAt: '2026-11-01T12:00:00Z',
    } : bankDirectory), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<BankListPage />, { queryClient: createDirectoryQueryClient({
      ...managerSession, capabilities: { ...managerSession.capabilities, syncExternalData: true },
    }) })
    await user.click(screen.getByRole('button', { name: updateBankRegistry ? 'Обновить данные банков' : 'Обновить ипотечные программы' }))
    expect(await screen.findByText('Источник временно недоступен')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Результат синхронизации банков' })).toHaveTextContent('создано 2, обновлено 3, обработано 5')
    const request = fetchMock.mock.calls.find(([path]) => path === '/api/v1/banks/sync/')
    expect(JSON.parse(request?.[1].body as string)).toEqual({ updateBankRegistry })
  })

  it('does not offer external synchronization to catalog moderators', () => {
    renderWithProviders(<BankListPage />, { queryClient: createDirectoryQueryClient(managerSession) })
    expect(screen.queryByRole('button', { name: 'Обновить данные банков' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Обновить ипотечные программы' })).not.toBeInTheDocument()
  })

  it('guards duplicate requests and shows a recoverable provider error', async () => {
    const user = userEvent.setup()
    let finish: (response: Response) => void = () => {}
    const fetchMock = vi.fn().mockImplementation(() => new Promise<Response>((resolve) => { finish = resolve }))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<BankListPage />, { queryClient: createDirectoryQueryClient({
      ...managerSession, capabilities: { ...managerSession.capabilities, syncExternalData: true },
    }) })
    await user.click(screen.getByRole('button', { name: 'Обновить ипотечные программы' }))
    expect(screen.getByRole('button', { name: 'Обновить данные банков' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Обновить ипотечные программы' })).toBeDisabled()
    finish(new Response(JSON.stringify({ detail: 'Источник банков временно недоступен' }), {
      status: 502, headers: { 'Content-Type': 'application/json' },
    }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Источник банков временно недоступен')
    expect(screen.getByRole('button', { name: 'Обновить ипотечные программы' })).toBeEnabled()
    expect(fetchMock).toHaveBeenCalledTimes(1)
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
    await user.selectOptions(scope, 'withPrograms')
    const parameters = new URLSearchParams({ q: 'Северный', scope: 'withPrograms' })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/banks/?${parameters}`,
      expect.objectContaining({ credentials: 'same-origin' }),
    ))

    await user.click(screen.getByRole('button', { name: 'Сбросить' }))
    expect(search).toHaveValue('')
    expect(scope).toHaveValue('all')
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
