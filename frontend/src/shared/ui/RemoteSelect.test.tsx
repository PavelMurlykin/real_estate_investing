import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { RemoteSelect } from './RemoteSelect'

describe('RemoteSelect', () => {
  it('filters complete form choices in one required input and exposes field errors', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    const changed = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<RemoteSelect searchable dictionary="cities" label="Город" value="2"
      required error="Выберите другой город." onChange={changed}
      initialOptions={[{ id: 1, label: 'Москва' }, { id: 2, label: 'Санкт-Петербург' }]} />)
    const input = screen.getByRole('combobox', { name: 'Город *' })
    expect(input).toBeRequired()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Выберите другой город.')
    expect(input).toHaveValue('Санкт-Петербург')
    expect(screen.queryByLabelText('Поиск: Город')).not.toBeInTheDocument()
    await user.click(input)
    await user.type(input, 'Моск')
    expect(screen.queryByRole('option', { name: 'Санкт-Петербург' })).not.toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(input).toHaveValue('Санкт-Петербург')
    await user.click(input)
    await user.type(input, 'Моск')
    await user.keyboard('{Enter}')
    expect(changed).toHaveBeenCalledWith('1', expect.objectContaining({ label: 'Москва' }))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('searches truncated form choices remotely with parent filters and selected IDs', async () => {
    const user = userEvent.setup()
    const changed = vi.fn()
    const fetchMock = vi.fn().mockImplementation(async (path: string) => {
      const query = new URL(path, 'http://localhost').searchParams.get('q')
      return Response.json({ page: 1, nextPage: null, totalCount: 1,
        results: [{ id: query ? 105 : 1, label: query ? 'Центр' : 'Первый город' }],
        selected: [{ id: 99, label: 'Сохранённый город' }],
      })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<RemoteSelect searchable dictionary="cities" label="Город" value="99"
      required onChange={changed} initialOptions={[]} truncated filters={{ regionId: 3 }} />)
    const input = screen.getByRole('combobox', { name: 'Город *' })
    await waitFor(() => expect(input).toHaveValue('Сохранённый город'))
    await user.click(input)
    await user.type(input, 'Центр')
    await user.click(await screen.findByRole('option', { name: 'Центр' }))
    expect(changed).toHaveBeenCalledWith('105', expect.objectContaining({ label: 'Центр' }))
    expect(fetchMock.mock.calls.some(([path]) => {
      const parameters = new URL(path, 'http://localhost').searchParams
      return parameters.get('q') === 'Центр' && parameters.get('regionId') === '3' && parameters.get('selectedIds') === '99'
    })).toBe(true)
  })

  it('preserves a selected value outside the page and searches on the server', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const fetchMock = vi.fn().mockImplementation(async (path: string) => {
      const parameters = new URL(path, 'http://localhost').searchParams
      const searched = parameters.get('q') === 'Центр'
      const secondPage = parameters.get('page') === '2'
      return new Response(JSON.stringify({
        results: [{ id: searched ? 105 : secondPage ? 2 : 1, label: searched ? 'Центр' : secondPage ? 'Вторая страница' : 'Первая страница' }],
        selected: [{ id: 99, label: 'Сохранённый город' }], totalCount: 105,
        page: secondPage ? 2 : 1, nextPage: searched || secondPage ? null : 2,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<RemoteSelect dictionary="cities" label="Город" value="99" onChange={onChange} />)
    await user.click(screen.getByRole('combobox', { name: 'Город' }))
    expect(await screen.findByRole('option', { name: 'Сохранённый город' })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.getByLabelText('Город')).toHaveValue('Сохранённый город')
    await user.click(screen.getByRole('combobox', { name: 'Город' }))
    await user.tab()
    expect(screen.getByRole('button', { name: 'Показать ещё варианты' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('option', { name: 'Вторая страница' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Город' })).toHaveFocus()
    await user.type(screen.getByRole('combobox', { name: 'Город' }), 'Центр')
    expect(await screen.findByRole('option', { name: 'Центр' })).toBeInTheDocument()
    await user.click(screen.getByRole('option', { name: 'Центр' }))
    expect(onChange).toHaveBeenCalledWith('105', expect.objectContaining({ label: 'Центр' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([path]) => String(path).includes('q='))).toBe(true))
  })

  it('offers retry after a dictionary request fails', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        results: [{ id: 1, label: 'Восстановленный город' }], selected: [], totalCount: 1, page: 1, nextPage: null,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<RemoteSelect dictionary="cities" label="Город" value="" onChange={vi.fn()} />)
    await user.click(screen.getByRole('combobox', { name: 'Город' }))
    await user.tab()
    await screen.findByRole('button', { name: 'Повторить загрузку справочника' })
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('option', { name: 'Восстановленный город' })).toBeInTheDocument()
  })
})
