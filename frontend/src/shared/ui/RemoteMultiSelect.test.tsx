import { screen, waitFor } from '@testing-library/react'
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
    expect(await screen.findByLabelText('Сохранённая планировка')).toBeChecked()
    await user.type(screen.getByLabelText('Поиск: Планировки'), 'Новая')
    await user.click(await screen.findByLabelText('Новая планировка'))
    expect(screen.getByLabelText('Сохранённая планировка')).toBeChecked()
    await waitFor(() => expect(screen.getByLabelText('Новая планировка')).toBeChecked())
    expect(fetchMock.mock.calls.some(([path]) => String(path).includes('selectedIds=205'))).toBe(true)
    await user.click(screen.getByLabelText('Сохранённая планировка'))
    await waitFor(() => expect(screen.queryByLabelText('Сохранённая планировка')).not.toBeInTheDocument())
    expect(screen.getByLabelText('Новая планировка')).toBeChecked()
  })
})
