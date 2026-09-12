import { screen, waitFor } from '@testing-library/react'
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
    expect(screen.getByRole('table')).toHaveAccessibleName(
      'Список ипотечных программ',
    )
    expect(screen.getAllByRole('link', { name: 'Семейная ипотека' })[0])
      .toHaveAttribute('href', '/mortgage-programs/5')
    expect(screen.queryByRole('link', { name: 'Добавить программу' }))
      .not.toBeInTheDocument()
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
