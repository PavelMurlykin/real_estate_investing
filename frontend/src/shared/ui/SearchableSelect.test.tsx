import { screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { RemoteSelect } from './RemoteSelect'
import { SearchableSelect } from './SearchableSelect'

function LocalFilter() {
  const [value, setValue] = useState('1')
  return <SearchableSelect label="Город" value={value} onChange={setValue}
    options={[{ value: '1', label: 'Москва' }, { value: '2', label: 'Тула' }]} />
}

describe('SearchableSelect', () => {
  it('combines editing and selection, resets through All and restores a choice on blur', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LocalFilter />)
    const input = screen.getByRole('combobox', { name: 'Город' })
    expect(input).toHaveValue('Москва')
    await user.click(input)
    await user.keyboard('{Enter}')
    expect(input).toHaveValue('Москва')
    await user.click(input)
    await user.type(input, 'Тул')
    const list = screen.getByRole('listbox', { name: 'Варианты: Город' })
    expect(within(list).queryByRole('option', { name: 'Москва' })).not.toBeInTheDocument()
    await user.click(within(list).getByRole('option', { name: 'Тула' }))
    expect(input).toHaveValue('Тула')
    expect(input).toHaveFocus()
    await user.click(input)
    await user.type(input, 'несохранённый поиск')
    await user.tab()
    expect(input).toHaveValue('Тула')
    await user.click(input)
    await user.click(screen.getByRole('option', { name: 'Все' }))
    expect(input).toHaveValue('')
    expect(input).toHaveAttribute('placeholder', 'Все')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('supports arrow keys, Enter and Escape without submitting a surrounding form', async () => {
    const user = userEvent.setup()
    const submitted = vi.fn((event) => event.preventDefault())
    renderWithProviders(<form onSubmit={submitted}><LocalFilter /></form>)
    const input = screen.getByRole('combobox', { name: 'Город' })
    await user.click(input)
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    expect(input).toHaveValue('Тула')
    expect(submitted).not.toHaveBeenCalled()
    await user.click(input)
    await user.type(input, 'Мос')
    await user.keyboard('{Escape}')
    expect(input).toHaveValue('Тула')
    expect(input).toHaveAttribute('aria-expanded', 'false')
  })

  it('selects a matching choice with Enter after typing rather than clearing the filter', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LocalFilter />)
    const input = screen.getByRole('combobox', { name: 'Город' })
    await user.click(input)
    await user.type(input, 'Тул')
    await user.keyboard('{Enter}')
    expect(input).toHaveValue('Тула')
    expect(input).toHaveAttribute('aria-expanded', 'false')
  })

  it('automatically loads remote filter choices and loads another page on scrolling', async () => {
    const user = userEvent.setup()
    const changed = vi.fn()
    const fetchMock = vi.fn().mockImplementation(async (path: string) => {
      const parameters = new URL(path, 'http://localhost').searchParams
      const next = parameters.get('page') === '2'
      return new Response(JSON.stringify({ page: next ? 2 : 1, nextPage: next ? null : 2, totalCount: 51,
        results: [{ id: next ? 51 : 1, label: next ? 'Последний город' : 'Первый город' }], selected: [],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<RemoteSelect filter dictionary="cities" label="Город" value="" initialOptions={[]} truncated onChange={changed} />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const input = screen.getByRole('combobox', { name: 'Город' })
    await user.click(input)
    expect(await screen.findByRole('option', { name: 'Первый город' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /варианты/ })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Поиск: Город')).not.toBeInTheDocument()
    const list = screen.getByRole('listbox', { name: 'Варианты: Город' })
    Object.defineProperties(list, { scrollHeight: { value: 1000 }, clientHeight: { value: 200 }, scrollTop: { value: 800, writable: true } })
    fireEvent.scroll(list)
    await user.click(await screen.findByRole('option', { name: 'Последний город' }))
    expect(changed).toHaveBeenCalledWith('51', expect.objectContaining({ label: 'Последний город' }))
    await user.click(input)
    await user.type(input, 'Последний')
    await waitFor(() => expect(fetchMock.mock.calls.some(([path]) => String(path).includes('q='))).toBe(true))
  })

  it('keeps choices stable while a search in the same dictionary is pending', async () => {
    const user = userEvent.setup()
    let finishSearch: (response: Response) => void = () => undefined
    const payload = { page: 1, nextPage: null, totalCount: 1, selected: [], results: [{ id: 205, label: 'Редкий город' }] }
    const fetchMock = vi.fn().mockImplementation((path: string) => {
      if (new URL(path, 'http://localhost').searchParams.has('q')) return new Promise<Response>((resolve) => { finishSearch = resolve })
      return Promise.resolve(new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    })
    vi.stubGlobal('fetch', fetchMock)
    const changed = vi.fn()
    renderWithProviders(<RemoteSelect filter dictionary="cities" label="Город" value="" initialOptions={[]} onChange={changed} />)
    await user.click(screen.getByRole('combobox', { name: 'Город' }))
    const originalChoice = await screen.findByRole('option', { name: 'Редкий город' })
    await user.type(screen.getByRole('combobox', { name: 'Город' }), 'Редкий')
    await waitFor(() => expect(fetchMock.mock.calls.some(([path]) => String(path).includes('q='))).toBe(true))
    expect(screen.getByRole('option', { name: 'Редкий город' })).toBe(originalChoice)
    finishSearch(new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    await user.click(originalChoice)
    expect(changed).toHaveBeenCalledWith('205', expect.objectContaining({ label: 'Редкий город' }))
  })

  it('does not offer stale choices after changing the parent scope', async () => {
    const user = userEvent.setup()
    let finishScope: (response: Response) => void = () => undefined
    const payload = (id: number, label: string) => ({ page: 1, nextPage: null, totalCount: 1, selected: [], results: [{ id, label }] })
    vi.stubGlobal('fetch', vi.fn().mockImplementation((path: string) => {
      if (new URL(path, 'http://localhost').searchParams.get('regionId') === '2') return new Promise<Response>((resolve) => { finishScope = resolve })
      return Promise.resolve(new Response(JSON.stringify(payload(1, 'Город первого региона')), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }))
    function ScopedFilter() {
      const [region, setRegion] = useState(1)
      return <><button onClick={() => setRegion(2)}>Сменить регион</button>
        <RemoteSelect filter dictionary="cities" label="Город" value="" onChange={vi.fn()} filters={{ regionId: region }}
          initialOptions={[{ id: 1, label: 'Город первого региона' }]} /></>
    }
    renderWithProviders(<ScopedFilter />)
    await user.click(screen.getByRole('combobox', { name: 'Город' }))
    expect(await screen.findByRole('option', { name: 'Город первого региона' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Сменить регион' }))
    await user.click(screen.getByRole('combobox', { name: 'Город' }))
    expect(screen.queryByRole('option', { name: 'Город первого региона' })).not.toBeInTheDocument()
    finishScope(new Response(JSON.stringify(payload(2, 'Город второго региона')), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    expect(await screen.findByRole('option', { name: 'Город второго региона' })).toBeInTheDocument()
  })
})
