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

const chart = [...history.results].reverse().map(({ meetingDate, keyRate }) => ({ meetingDate, keyRate }))

function keyRateQueryClient(session?: Session, data = history) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['key-rates', ''], data)
  queryClient.setQueryData(['key-rates', 'chart'], chart)
  if (session) queryClient.setQueryData(['session'], session)
  return queryClient
}

describe('KeyRatePage', () => {
  it('shows the chart above the history table and removes the previous controls', () => {
    renderWithProviders(<KeyRatePage />, {
      queryClient: keyRateQueryClient(),
    })

    expect(screen.getByRole('heading', { name: 'Ключевая ставка' }))
      .toBeInTheDocument()
    const chartImage = screen.getByRole('img', { name: 'Динамика ключевой ставки' })
    expect(screen.getByText(/Минимум/)).toHaveTextContent('10% · 01.01.2026')
    expect(screen.getByText(/Максимум/)).toHaveTextContent('12% · 01.02.2026')
    const table = screen.getByRole('table', {
      name: 'История ключевой ставки Банка России',
    })
    expect(chartImage.compareDocumentPosition(table)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    expect(within(table).getByText('↑ 2 п.п.')).toHaveClass(
      'key-rate-change--up',
    )
    expect(screen.queryByRole('button', { name: 'Обновить из ЦБ РФ' }))
      .not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Прежняя версия' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Поиск по истории ставки')).not.toBeInTheDocument()
    expect(screen.queryByText('Текущая ставка')).not.toBeInTheDocument()
  })

  it('refreshes the table and chart when an administrator imports a retained rate', async () => {
    const user = userEvent.setup()
    const latest = { meetingDate: '2026-03-01', keyRate: '12.00' }
    const refreshedHistory = {
      ...history,
      totalCount: 3,
      currentRate: latest,
      results: [{ ...history.results[0], ...latest, id: 3, rateChange: '0.00' }, ...history.results],
    }
    const syncResult = {
      created: 1,
      updated: 0,
      processed: 3,
      currentRate: latest,
      synchronizedAt: '2026-02-03T10:00:00Z',
    }
    const responses: Record<string, unknown> = {
      '/api/v1/key-rates/sync/': syncResult,
      '/api/v1/key-rates/': refreshedHistory,
      '/api/v1/key-rates/chart/': [...chart, latest],
    }
    const fetchMock = vi.fn(async (url: string) => Response.json(responses[url]))
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
      'Обработано 3, добавлено 1, обновлено 0',
    )
    expect(screen.getByRole('row', { name: /01.03.2026.*0 п.п./ })).toBeInTheDocument()
    expect(screen.getByText(/Последняя запись/)).toHaveTextContent('12% · 01.03.2026')
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
    expect(screen.getByRole('img', { name: 'Динамика ключевой ставки' })).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/v1/key-rates/chart/', expect.anything())
  })
})
