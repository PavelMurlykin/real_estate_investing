import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { NationalLocationUpdateAction } from './NationalLocationUpdateAction'

const job = {
  id: '382079fb-2acf-48e1-a8ba-47d49a468d55', status: 'running', phase: 'districts',
  processedCities: 10, totalCities: 1117, currentCity: 'Казань', counts: {},
  coverage: {}, errorMessage: '', updatedAt: '2026-11-15T10:00:00Z',
}

describe('NationalLocationUpdateAction', () => {
  it('starts a national import without parent filters and restores progress', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((_url, options) => Promise.resolve(
      Response.json({ job: options?.method === 'POST' ? job : null }),
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<NationalLocationUpdateAction />)
    const button = screen.getByRole('button', { name: 'Обновить данные' })
    expect(screen.getAllByRole('button')).toEqual([button])
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    await user.click(button)
    expect(await screen.findByRole('status')).toHaveTextContent('Обработано населённых пунктов 10')
    expect(button).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/location-imports/', expect.objectContaining({ method: 'POST', body: '{}' }))
  })

  it('restores a running job after opening the page again', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(Response.json({ job })))
    renderWithProviders(<NationalLocationUpdateAction />)
    expect(await screen.findByRole('status')).toHaveTextContent('Обработано населённых пунктов 10')
    expect(screen.getByRole('button', { name: 'Обновить данные' })).toBeDisabled()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('allows a failed job to resume and allows another run after completion', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json({ job: { ...job, status: 'failed', errorMessage: 'Источник недоступен.' } }))
      .mockResolvedValueOnce(Response.json({ job: { ...job, status: 'completed', processedCities: 1117 } })))
    renderWithProviders(<NationalLocationUpdateAction />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Источник недоступен.')
    await user.click(screen.getByRole('button', { name: 'Обновить данные' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Справочники обновлены')
    expect(screen.getByRole('button', { name: 'Обновить данные' })).toBeEnabled()
  })

  it('recovers when the start response has an unexpected format', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation((_url, options) => Promise.resolve(
      Response.json(options?.method === 'POST' ? { bad: true } : { job: null }),
    )))
    renderWithProviders(<NationalLocationUpdateAction />)
    const button = screen.getByRole('button', { name: 'Обновить данные' })
    await user.click(button)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    await waitFor(() => expect(button).toBeEnabled())
  })
})
