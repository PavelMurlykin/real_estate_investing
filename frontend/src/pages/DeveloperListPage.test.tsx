import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type {
  DeveloperListResponse,
  DeveloperOptions,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { DeveloperListPage } from './DeveloperListPage'

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

const administratorSession: Session = {
  ...managerSession,
  user: {
    id: 2,
    displayName: 'Администратор',
    email: 'administrator@example.com',
    agencyName: '',
  },
  capabilities: {
    ...managerSession.capabilities,
    syncExternalData: true,
    viewAllPrivateRecords: true,
  },
}

const directory: DeveloperListResponse = {
  page: 1,
  pageSize: 20,
  totalCount: 1,
  totalPages: 1,
  results: [
    {
      id: 7,
      name: 'Северный девелопер',
      companyGroup: { id: 4, name: 'Группа Север' },
      regions: [{ id: 8, name: 'Санкт-Петербург' }],
      complexCount: 3,
      isActive: true,
    },
  ],
}

const options: DeveloperOptions = {
  companyGroups: [{ id: 4, name: 'Группа Север' }],
  regions: [{ id: 8, name: 'Санкт-Петербург' }],
  truncated: {
    companyGroups: false,
    regions: false,
  },
}

function createDirectoryQueryClient(session?: Session) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['developers', ''], directory)
  queryClient.setQueryData(['developer-options'], options)
  if (session) queryClient.setQueryData(['session'], session)
  return queryClient
}

describe('DeveloperListPage', () => {
  it('renders only the safe public developer directory fields', () => {
    renderWithProviders(<DeveloperListPage />, {
      queryClient: createDirectoryQueryClient(),
    })

    expect(
      screen.getByRole('heading', { name: 'Застройщики' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveAccessibleName(
      'Список застройщиков',
    )
    expect(screen.getAllByText('Северный девелопер')).toHaveLength(2)
    expect(screen.getAllByText('Группа Север').length).toBeGreaterThan(1)
    expect(screen.queryByText('ИНН')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Добавить застройщика' }))
      .not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Импорт реестра ЕРЗ' }))
      .not.toBeInTheDocument()
  })

  it('filters through URL state and requests the selected company group', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(directory), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<DeveloperListPage />, {
      queryClient: createDirectoryQueryClient(),
    })

    await user.selectOptions(
      screen.getByLabelText('Группа компаний'),
      '4',
    )

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/developers/?companyGroupId=4',
      expect.objectContaining({ credentials: 'same-origin' }),
    ))
  })

  it('shows React management routes to catalog managers', () => {
    renderWithProviders(<DeveloperListPage />, {
      queryClient: createDirectoryQueryClient(managerSession),
    })

    expect(screen.getByRole('link', { name: 'Добавить застройщика' }))
      .toHaveAttribute('href', '/developers/new')
    expect(
      screen.getByRole('link', {
        name: 'Редактировать: Северный девелопер',
      }),
    ).toHaveAttribute('href', '/developers/7/edit')
    expect(screen.queryByRole('heading', { name: 'Импорт реестра ЕРЗ' }))
      .not.toBeInTheDocument()
  })

  it('shows the React registry import only to application administrators', () => {
    renderWithProviders(<DeveloperListPage />, {
      queryClient: createDirectoryQueryClient(administratorSession),
    })

    expect(screen.getByRole('heading', { name: 'Импорт реестра ЕРЗ' }))
      .toBeInTheDocument()
    expect(screen.getByLabelText('Файл ЕРЗ')).toBeInTheDocument()
  })

  it('deletes an unused developer after explicit confirmation', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn<typeof fetch>((_input, requestOptions) => {
      if (requestOptions?.method === 'DELETE') {
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      return Promise.resolve(
        new Response(JSON.stringify({
          ...directory,
          totalCount: 0,
          results: [],
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<DeveloperListPage />, {
      queryClient: createDirectoryQueryClient(managerSession),
    })

    await user.click(
      screen.getByRole('button', {
        name: 'Удалить: Северный девелопер',
      }),
    )
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveAccessibleName('Удалить застройщика?')
    expect(within(dialog).getByRole('button', { name: 'Отмена' })).toHaveFocus()
    await user.click(within(dialog).getByRole('button', { name: 'Удалить' }))

    await waitFor(() => expect(screen.queryByRole('alertdialog'))
      .not.toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/developers/7/',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('explains why a developer linked to complexes cannot be deleted', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Связаны ЖК.' }), {
          status: 409,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    renderWithProviders(<DeveloperListPage />, {
      queryClient: createDirectoryQueryClient(managerSession),
    })

    await user.click(
      screen.getByRole('button', {
        name: 'Удалить: Северный девелопер',
      }),
    )
    const dialog = screen.getByRole('alertdialog')
    await user.click(within(dialog).getByRole('button', { name: 'Удалить' }))

    expect(
      await within(dialog).findByText(
        'Сначала удалите или переназначьте связанные ЖК.',
      ),
    ).toBeInTheDocument()
  })
})
