import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { MetroUpdateAction } from './MetroUpdateAction'

const result = {
  created: 2, updated: 1, unchanged: 4, skipped: 0,
  lines: { created: 1, updated: 0, unchanged: 0 },
  source: 'Wikimedia / HFLabs', sourceUrl: 'https://www.wikidata.org/wiki/Wikidata:Data_access',
}

describe('MetroUpdateAction', () => {
  it('accepts source metadata changes and allows retry after an invalid result', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json({ ...result, created: 'bad' }))
      .mockResolvedValueOnce(Response.json({ ...result, source: 'OpenStreetMap', sourceUrl: 'https://www.openstreetmap.org/copyright' })))
    renderWithProviders(<MetroUpdateAction systemId="9" />)
    const button = screen.getByRole('button', { name: 'Обновить данные' })
    await user.click(button)
    expect(await screen.findByRole('alert')).toHaveTextContent('Сервер вернул данные в неожиданном формате.')
    expect(button).toBeEnabled()
    await user.click(button)
    expect(await screen.findByText(/Станции обновлены/)).toBeInTheDocument()
    expect(button).toBeEnabled()
  })

  it('releases the button without waiting for list refresh', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(Response.json(result)))
    const { queryClient } = renderWithProviders(<MetroUpdateAction systemId="9" />)
    vi.spyOn(queryClient, 'invalidateQueries').mockImplementation(() => new Promise(() => undefined))
    const button = screen.getByRole('button', { name: 'Обновить данные' })
    await user.click(button)
    expect(await screen.findByText(/Станции обновлены/)).toBeInTheDocument()
    expect(button).toBeEnabled()
  })
  it('requires a system and shows no status before import', () => {
    renderWithProviders(<MetroUpdateAction systemId="" />)
    expect(screen.getByRole('button', { name: 'Обновить данные' })).toBeDisabled()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('imports the selected system, prevents duplicates and refreshes dictionaries', async () => {
    const user = userEvent.setup()
    let resolveRequest: (response: Response) => void = () => undefined
    const fetchMock = vi.fn<typeof fetch>(() => new Promise((resolve) => { resolveRequest = resolve }))
    vi.stubGlobal('fetch', fetchMock)
    const { queryClient } = renderWithProviders(<MetroUpdateAction systemId="9" />)
    queryClient.setQueryData(['location-dictionaries', 'metro', ''], {})
    queryClient.setQueryData(['catalog-options', 'metro-lines'], {})
    const button = screen.getByRole('button', { name: 'Обновить данные' })
    await user.click(button)
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/location-dictionaries/metro/import/', expect.objectContaining({
      method: 'POST', credentials: 'same-origin', body: JSON.stringify({ systemId: 9 }),
    }))
    resolveRequest(Response.json(result))
    expect(await screen.findByText(/Станции обновлены. Добавлено 2, обновлено 1/)).toBeInTheDocument()
    expect(queryClient.getQueryState(['location-dictionaries', 'metro', ''])?.isInvalidated).toBe(true)
    expect(queryClient.getQueryState(['catalog-options', 'metro-lines'])?.isInvalidated).toBe(true)
    expect(button).toBeEnabled()
  })

  it('shows a source error and supports an explicit retry', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json({ detail: 'Источник временно недоступен.' }, { status: 502 }))
      .mockResolvedValueOnce(Response.json(result))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<MetroUpdateAction systemId="9" />)
    await user.click(screen.getByRole('button', { name: 'Обновить данные' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Источник временно недоступен.')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: 'Обновить данные' }))
    await waitFor(() => expect(screen.getByText(/Станции обновлены/)).toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string)).toEqual({ systemId: 9 })
  })
})
