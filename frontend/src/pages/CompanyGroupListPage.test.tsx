import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { CompanyGroupListResponse, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { CompanyGroupListPage } from './CompanyGroupListPage'

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

const directory: CompanyGroupListResponse = {
  page: 1,
  pageSize: 20,
  totalCount: 1,
  totalPages: 1,
  results: [
    {
      id: 7,
      name: 'Группа Север',
      developerCount: 3,
      legacyEditUrl: '/property/company-groups/7/update/',
      legacyDeleteUrl: '/property/company-groups/7/delete/',
    },
  ],
}

function createDirectoryQueryClient(session?: Session) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['company-groups', ''], directory)
  if (session) queryClient.setQueryData(['session'], session)
  return queryClient
}

describe('CompanyGroupListPage', () => {
  it('renders the public paginated directory without management actions', () => {
    renderWithProviders(<CompanyGroupListPage />, {
      queryClient: createDirectoryQueryClient(),
    })

    expect(
      screen.getByRole('heading', { name: 'Группы компаний' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveAccessibleName(
      'Список групп компаний',
    )
    expect(screen.getAllByText('Группа Север')).toHaveLength(2)
    expect(screen.queryByRole('link', { name: 'Добавить группу' }))
      .not.toBeInTheDocument()
  })

  it('shows React management routes to catalog managers', () => {
    renderWithProviders(<CompanyGroupListPage />, {
      queryClient: createDirectoryQueryClient(managerSession),
    })

    expect(screen.getByRole('link', { name: 'Добавить группу' }))
      .toHaveAttribute('href', '/company-groups/new')
    expect(
      screen.getByRole('link', { name: 'Редактировать: Группа Север' }),
    ).toHaveAttribute('href', '/company-groups/7/edit')
  })

  it('deletes an unused group after explicit confirmation', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn<typeof fetch>((_input, options) => {
      if (options?.method === 'DELETE') {
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      return Promise.resolve(
        new Response(JSON.stringify({
          ...directory,
          totalCount: 0,
          totalPages: 0,
          results: [],
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<CompanyGroupListPage />, {
      queryClient: createDirectoryQueryClient(managerSession),
    })

    await user.click(
      screen.getByRole('button', { name: 'Удалить: Группа Север' }),
    )
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveAccessibleName('Удалить группу компаний?')
    expect(within(dialog).getByRole('button', { name: 'Отмена' })).toHaveFocus()
    await user.click(within(dialog).getByRole('button', { name: 'Удалить' }))

    await waitFor(() => expect(screen.queryByRole('alertdialog'))
      .not.toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/company-groups/7/',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('explains why a group linked to developers cannot be deleted', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Связаны застройщики.' }), {
          status: 409,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    renderWithProviders(<CompanyGroupListPage />, {
      queryClient: createDirectoryQueryClient(managerSession),
    })

    await user.click(
      screen.getByRole('button', { name: 'Удалить: Группа Север' }),
    )
    const dialog = screen.getByRole('alertdialog')
    await user.click(within(dialog).getByRole('button', { name: 'Удалить' }))

    expect(
      await within(dialog).findByText(
        'Сначала отвяжите от группы всех застройщиков.',
      ),
    ).toBeInTheDocument()
  })
})
