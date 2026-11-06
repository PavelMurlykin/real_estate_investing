import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { MortgageProgramListResponse, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { MortgageProgramListPage } from './MortgageProgramListPage'

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
const directory: MortgageProgramListResponse = {
  page: 1,
  pageSize: 20,
  totalCount: 1,
  totalPages: 1,
  results: [{
    id: 5,
    name: 'Семейная ипотека',
    condition: 'Для семей с детьми',
    isPreferential: true,
    creditLimit: '12000000.00',
    bankCount: 2,
    developerProgramCount: 1,
    regionalLimitCount: 1,
    aliasCount: 2,
    isActive: true,
    updatedAt: '2026-01-11T10:00:00Z',
    detailUrl: '/mortgage-programs/5',
    legacyEditUrl: '/bank/?model=mortgage_program&edit=5',
  }],
}

function queryClient(session?: Session) {
  const client = createTestQueryClient()
  client.setQueryData(['mortgage-programs', ''], directory)
  if (session) client.setQueryData(['session'], session)
  return client
}

describe('MortgageProgramListPage', () => {
  it('renders a public program directory with React links', () => {
    renderWithProviders(<MortgageProgramListPage />, { queryClient: queryClient() })

    expect(screen.getByRole('heading', { name: 'Ипотечные программы' }))
      .toBeInTheDocument()
    const table = within(screen.getByRole('table', { name: 'Список ипотечных программ' }))
    expect(table.getAllByRole('columnheader')).toHaveLength(4)
    for (const name of ['Программа', 'Описание', 'Тип', 'Кредитный лимит']) {
      expect(table.getByRole('columnheader', { name })).toBeInTheDocument()
    }
    expect(table.getByRole('link', { name: 'Семейная ипотека' }))
      .toHaveAttribute('href', '/mortgage-programs/5')
    expect(table.getByRole('cell', { name: 'Для семей с детьми' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Добавить программу' }))
      .not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Прежняя версия' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Найти' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Статус')).not.toBeInTheDocument()
  })

  it('searches while typing and resets search and type together', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async () => Response.json(directory))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<MortgageProgramListPage />, {
      initialRoute: '/mortgage-programs?status=inactive',
      queryClient: queryClient(),
    })

    await user.type(screen.getByRole('searchbox', { name: 'Поиск' }), 'дети')
    const query = new URLSearchParams({ q: 'дети' })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/mortgage-programs/?${query}`,
      expect.objectContaining({ credentials: 'same-origin' }),
    ))
    await user.selectOptions(screen.getByLabelText('Тип программы'), 'market')
    await user.click(within(screen.getByRole('search')).getByRole('button', { name: 'Сбросить' }))

    expect(screen.getByRole('searchbox', { name: 'Поиск' })).toHaveValue('')
    expect(screen.getByLabelText('Тип программы')).toHaveValue('all')
  })

  it('stores the selected type in the URL and reloads the directory', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify(directory),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<MortgageProgramListPage />, { queryClient: queryClient() })

    await user.selectOptions(screen.getByLabelText('Тип программы'), 'market')

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/mortgage-programs/?programType=market',
      expect.objectContaining({ credentials: 'same-origin' }),
    ))
  })

  it('shows React create and edit routes to catalog managers', () => {
    renderWithProviders(<MortgageProgramListPage />, {
      queryClient: queryClient(manager),
    })

    expect(screen.getByRole('link', { name: 'Добавить программу' }))
      .toHaveAttribute('href', '/mortgage-programs/new')
    expect(screen.getByRole('link', { name: 'Редактировать: Семейная ипотека' }))
      .toHaveAttribute('href', '/mortgage-programs/5/edit')
  })
})
