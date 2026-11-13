import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { RemoteMultiSelect } from './RemoteMultiSelect'

function Preferences() {
  const [values, setValues] = useState(['205'])
  return <RemoteMultiSelect dictionary="layouts" label="Планировки" values={values} onChange={setValues}
    initialOptions={[{ id: 1, label: 'Студия' }]} truncated />
}

describe('RemoteMultiSelect', () => {
  it('adds and removes local choices with the keyboard without submitting or fetching', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    const submitted = vi.fn((event) => event.preventDefault())
    vi.stubGlobal('fetch', fetchMock)
    function LocalChoices() {
      const [values, setValues] = useState(['1'])
      return <form onSubmit={submitted}><RemoteMultiSelect dictionary="layouts" label="Планировки"
        values={values} onChange={setValues}
        initialOptions={[{ id: 1, label: 'Студия' }, { id: 2, label: 'Евродвушка' }, { id: 3, label: 'Трёхкомнатная' }]} />
        <button type="submit">Сохранить</button></form>
    }
    renderWithProviders(<LocalChoices />)
    const input = screen.getByRole('combobox', { name: 'Планировки' })
    await user.click(input)
    await user.type(input, 'ЕВРО')
    const list = screen.getByRole('listbox', { name: 'Варианты: Планировки' })
    expect(list).toHaveAttribute('aria-multiselectable', 'true')
    expect(within(list).queryByRole('option', { name: 'Студия' })).not.toBeInTheDocument()
    await user.keyboard('{Enter}{Escape}')
    expect(screen.getByRole('button', { name: 'Убрать: Студия' })).toBeInTheDocument()
    const remove = screen.getByRole('button', { name: 'Убрать: Евродвушка' })
    await user.click(input)
    await user.type(input, 'несуществующее')
    await user.keyboard('{Enter}{Escape}')
    expect(remove).toBeInTheDocument()
    await user.tab({ shift: true })
    expect(remove).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(input).toHaveFocus()
    expect(remove).not.toBeInTheDocument()
    await user.click(input)
    await user.click(screen.getByRole('option', { name: 'Очистить выбор' }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('list', { name: 'Выбрано: Планировки' })).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(submitted).not.toHaveBeenCalled()
  })

  it('keeps disabled selections visible and connects validation errors to the field', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<RemoteMultiSelect dictionary="regions" label="Регионы" values={['1']}
      onChange={vi.fn()} disabled error="Выберите другой регион."
      initialOptions={[{ id: 1, label: 'Москва' }]} />)
    const input = screen.getByRole('combobox', { name: 'Регионы' })
    expect(input).toBeDisabled()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Выберите другой регион.')
    expect(screen.getByRole('button', { name: 'Убрать: Москва' })).toBeDisabled()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('loads omitted selections and preserves them while searching and adding another choice', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockImplementation(async (path: string) => {
      const parameters = new URL(path, 'http://localhost').searchParams
      return new Response(JSON.stringify({
        results: parameters.has('q') ? [{ id: 300, label: 'Новая планировка' }] : [],
        selected: parameters.getAll('selectedIds').map((id) => ({ id: Number(id), label: id === '205' ? 'Сохранённая планировка' : 'Новая планировка' })),
        totalCount: 1, page: 1, nextPage: null,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<Preferences />)
    expect(await screen.findByRole('button', { name: 'Убрать: Сохранённая планировка' })).toBeInTheDocument()
    await user.click(screen.getByRole('combobox', { name: 'Планировки' }))
    await user.type(screen.getByRole('combobox', { name: 'Планировки' }), 'Новая')
    await user.click(await screen.findByRole('option', { name: 'Новая планировка' }))
    expect(screen.getByRole('button', { name: 'Убрать: Сохранённая планировка' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Убрать: Новая планировка' })).toBeInTheDocument())
    expect(fetchMock.mock.calls.some(([path]) => String(path).includes('selectedIds=205'))).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Убрать: Сохранённая планировка' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Убрать: Сохранённая планировка' })).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Убрать: Новая планировка' })).toBeInTheDocument()
  })
})
