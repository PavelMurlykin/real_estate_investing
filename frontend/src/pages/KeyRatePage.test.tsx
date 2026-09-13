import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { KeyRateListResponse, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { KeyRatePage } from './KeyRatePage'

const history: KeyRateListResponse = {
  page: 1,
  pageSize: 20,
  totalCount: 2,
  totalPages: 1,
  currentRate: { meetingDate: '2026-02-01', keyRate: '12.00' },
  lastSyncedAt: '2026-02-02T10:00:00Z',
  legacyUrl: '/bank/key-rate/',
  results: [
    {
      id: 2,
      meetingDate: '2026-02-01',
      keyRate: '12.00',
      rateChange: '2.00',
      isActive: true,
      updatedAt: '2026-02-02T10:00:00Z',
    },
    {
      id: 1,
      meetingDate: '2026-01-01',
      keyRate: '10.00',
      rateChange: null,
      isActive: true,
      updatedAt: '2026-01-02T10:00:00Z',
    },
  ],
}

const administrator: Session = {
  isAuthenticated: true,
  user: {
    id: 1,
    displayName: 'Администратор',
    email: 'admin@example.com',
    agencyName: '',
  },
  capabilities: {
    manageCatalogs: true,
    syncExternalData: true,
    viewPrivateRecords: true,
    viewAllPrivateRecords: true,
  },
}

function keyRateQueryClient(session?: Session, data = history) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['key-rates', ''], data)
  if (session) queryClient.setQueryData(['session'], session)
  return queryClient
}

describe('KeyRatePage', () => {
  it('renders the public current rate and chronological history', () => {
    renderWithProviders(<KeyRatePage />, {
      queryClient: keyRateQueryClient(),
    })

    expect(screen.getByRole('heading', { name: 'Ключевая ставка' }))
      .toBeInTheDocument()
    expect(screen.getAllByText('12%').length).toBeGreaterThan(0)
    expect(screen.getByText('Действует с 01.02.2026')).toBeInTheDocument()
    const table = screen.getByRole('table', {
      name: 'История изменений ключевой ставки Банка России',
    })
    expect(within(table).getByText('↑ 2%')).toHaveClass(
      'key-rate-change--up',
    )
    expect(screen.queryByRole('button', { name: 'Обновить из ЦБ РФ' }))
      .not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Прежняя версия' }))
      .toHaveAttribute('href', '/bank/key-rate/')
  })

  it('lets an administrator synchronize data and reports counts', async () => {
    const user = userEvent.setup()
    const syncResult = {
      created: 2,
      updated: 1,
      processed: 8,
      currentRate: history.currentRate,
      synchronizedAt: '2026-02-03T10:00:00Z',
    }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(syncResult), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify(history), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<KeyRatePage />, {
      queryClient: keyRateQueryClient(administrator),
    })

    await user.click(screen.getByRole('button', { name: 'Обновить из ЦБ РФ' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/key-rates/sync/',
      expect.objectContaining({ method: 'POST' }),
    ))
    expect(await screen.findByRole('status')).toHaveTextContent(
      'обработано 8, добавлено 2, обновлено 1',
    )
  })

  it('stores pagination in the URL and requests the selected page', async () => {
    const user = userEvent.setup()
    const paginatedHistory = { ...history, totalCount: 21, totalPages: 2 }
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ ...paginatedHistory, page: 2 }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<KeyRatePage />, {
      queryClient: keyRateQueryClient(undefined, paginatedHistory),
    })

    await user.click(screen.getByRole('button', { name: 'Далее' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/key-rates/?page=2',
      expect.objectContaining({ credentials: 'same-origin' }),
    ))
  })
})
