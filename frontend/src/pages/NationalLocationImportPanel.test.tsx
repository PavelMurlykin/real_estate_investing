import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { NationalLocationImportPanel } from './NationalLocationImportPanel'

const job = {
  id: '382079fb-2acf-48e1-a8ba-47d49a468d55', status: 'running', phase: 'districts',
  processedCities: 10, totalCities: 1117, currentCity: 'Казань', counts: {},
  coverage: {}, errorMessage: '', updatedAt: '2026-11-15T10:00:00Z',
}

describe('NationalLocationImportPanel', () => {
  it('starts a national import without parent filters and restores progress', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((_url, options) => Promise.resolve(
      Response.json({ job: options?.method === 'POST' ? job : null }),
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<NationalLocationImportPanel />)
    await user.click(screen.getByRole('button', { name: 'Импортировать все населённые пункты России' }))
    expect(await screen.findByRole('status')).toHaveTextContent('10 из 1117')
    expect(screen.getByRole('button', { name: 'Общий импорт выполняется…' })).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/location-imports/', expect.objectContaining({ method: 'POST', body: '{}' }))
  })

  it('restores a running job after opening the page again', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(Response.json({ job })))
    renderWithProviders(<NationalLocationImportPanel />)
    expect(await screen.findByRole('status')).toHaveTextContent('Казань')
    expect(screen.getByRole('progressbar')).toHaveAttribute('value', '10')
  })

  it('allows a failed job to resume and allows another run after completion', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json({ job: { ...job, status: 'failed', errorMessage: 'Источник недоступен.' } }))
      .mockResolvedValueOnce(Response.json({ job: { ...job, status: 'completed', processedCities: 1117 } })))
    renderWithProviders(<NationalLocationImportPanel />)
    await user.click(await screen.findByRole('button', { name: 'Продолжить импорт России' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Общий импорт завершён')
    expect(screen.getByRole('button', { name: 'Импортировать все населённые пункты России' })).toBeEnabled()
  })

  it('recovers when the start response has an unexpected format', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation((_url, options) => Promise.resolve(
      Response.json(options?.method === 'POST' ? { bad: true } : { job: null }),
    )))
    renderWithProviders(<NationalLocationImportPanel />)
    const button = screen.getByRole('button', { name: 'Импортировать все населённые пункты России' })
    await user.click(button)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    await waitFor(() => expect(button).toBeEnabled())
  })
})
