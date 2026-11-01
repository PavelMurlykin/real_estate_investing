import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { RemoteSelect } from './RemoteSelect'

describe('RemoteSelect', () => {
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
    expect(await screen.findByRole('option', { name: 'Сохранённый город' })).toBeInTheDocument()
    expect(screen.getByLabelText('Город')).toHaveValue('99')
    await user.click(screen.getByRole('button', { name: 'Показать ещё варианты' }))
    expect(await screen.findByRole('option', { name: 'Вторая страница' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Поиск: Город'), 'Центр')
    expect(await screen.findByRole('option', { name: 'Центр' })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Город'), '105')
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
    await user.click(await screen.findByRole('button', { name: 'Повторить загрузку справочника' }))
    expect(await screen.findByRole('option', { name: 'Восстановленный город' })).toBeInTheDocument()
  })
})
