import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { ComplexImport } from './ComplexImport'

const result = { created: 1, updated: 0, photos: 0, buildings: 1, metro: 0 }

describe('ComplexImport', () => {
  it('shows both formats and allows importing again while catalog refresh is pending', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json(result))
    vi.stubGlobal('fetch', fetchMock)
    const { queryClient } = renderWithProviders(<ComplexImport />)
    vi.spyOn(queryClient, 'invalidateQueries').mockImplementation(() => new Promise(() => undefined))
    await user.click(screen.getByText('Импорт жилых комплексов из JSON'))
    expect(screen.getByText(/Версия 2 использует ID/)).toBeInTheDocument()
    const upload = screen.getByLabelText('Файл JSON')
    await user.upload(upload, new File([JSON.stringify({ version: 2, complexes: [] })], 'complexes.json', { type: 'application/json' }))
    const button = screen.getByRole('button', { name: 'Импортировать' })
    await user.click(button)
    expect(await screen.findByRole('status')).toHaveTextContent('Создано ЖК 1')
    expect(button).toBeEnabled()
    await user.click(button)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  })

  it('keeps the file and releases the button after a server validation error', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json({ detail: 'Неоднозначный населённый пункт.' }, { status: 400 }))
      .mockResolvedValueOnce(Response.json(result)))
    renderWithProviders(<ComplexImport />)
    await user.click(screen.getByText('Импорт жилых комплексов из JSON'))
    await user.upload(screen.getByLabelText('Файл JSON'), new File(['{}'], 'complexes.json', { type: 'application/json' }))
    const button = screen.getByRole('button', { name: 'Импортировать' })
    await user.click(button)
    expect(await screen.findByRole('alert')).toHaveTextContent('Неоднозначный населённый пункт.')
    expect(button).toBeEnabled()
    await user.click(button)
    expect(await screen.findByRole('status')).toHaveTextContent('Создано ЖК 1')
  })
})
