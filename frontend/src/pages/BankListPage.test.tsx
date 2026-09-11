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
  })

  it('stores program filters in the URL and requests filtered rows', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(bankDirectory), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<BankListPage />, {
      queryClient: createDirectoryQueryClient(),
    })

    await user.selectOptions(screen.getByLabelText('Программы'), 'withPrograms')

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/banks/?scope=withPrograms',
      expect.objectContaining({ credentials: 'same-origin' }),
    ))
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
