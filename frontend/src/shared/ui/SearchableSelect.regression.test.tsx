import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '@/test/render'
import { RemoteSelect } from './RemoteSelect'
import { RemoteMultiSelect } from './RemoteMultiSelect'
import { SearchableSelect, SearchableMultiSelect } from './SearchableSelect'

describe('dictionary recovery', () => {
  it.each([false, true])('preserves an unresolved selection on Enter after a failed lookup (multiple: %s)', async (multiple) => {
    const user = userEvent.setup()
    const changed = vi.fn()
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 503 })))
    renderWithProviders(multiple
      ? <RemoteMultiSelect dictionary="cities" label="Город" values={['42']} initialOptions={[]} onChange={changed} />
      : <RemoteSelect filter dictionary="cities" label="Город" value="42" initialOptions={[]} onChange={changed} />)
    const input = screen.getByRole('combobox', { name: 'Город' })
    await user.click(input)
    await screen.findByRole('button', { name: 'Повторить загрузку справочника' })
    await user.keyboard('{Enter}')
    expect(changed).not.toHaveBeenCalled()
  })

  it.each([false, true])('blocks implicit clearing but retains explicit cached choices while loading (multiple: %s)', async (multiple) => {
    const user = userEvent.setup()
    const changed = vi.fn()
    const options = [{ value: '2', label: 'Тула' }]
    renderWithProviders(multiple
      ? <SearchableMultiSelect label="Город" values={['42']} options={options} loading onChange={changed} />
      : <SearchableSelect label="Город" value="42" options={options} loading onChange={changed} />)
    await user.click(screen.getByRole('combobox', { name: 'Город' }))
    await user.keyboard('{Enter}')
    expect(changed).not.toHaveBeenCalled()
    await user.click(screen.getByRole('option', { name: 'Тула' }))
    expect(changed).toHaveBeenCalledWith(multiple ? ['42', '2'] : '2')
  })

  it('locks an asynchronous retry and retains keyboard focus and the search text', async () => {
    const user = userEvent.setup()
    let finish: () => void = () => undefined
    const retry = vi.fn(() => new Promise<void>((resolve) => { finish = resolve }))
    renderWithProviders(<SearchableSelect label="Город" value="42" options={[]} error onRetry={retry} onChange={vi.fn()} />)
    const input = screen.getByRole('combobox', { name: 'Город' })
    await user.type(input, 'Мос')
    const button = screen.getByRole('button', { name: 'Повторить загрузку справочника' })
    await user.tab()
    await user.keyboard('{Enter}')
    expect(input).toHaveFocus()
    expect(input).toHaveValue('Мос')
    expect(button).toBeDisabled()
    expect(input).toHaveAttribute('aria-busy', 'true')
    await user.click(button)
    expect(retry).toHaveBeenCalledTimes(1)
    await user.click(input)
    await act(async () => finish())
    await waitFor(() => expect(screen.getByRole('button', { name: 'Повторить загрузку справочника' })).toBeEnabled())
  })

  it('keeps cached choices and deliberate clearing available after a lookup error', async () => {
    const user = userEvent.setup()
    const changed = vi.fn()
    renderWithProviders(<SearchableSelect label="Город" value="1" options={[{ value: '1', label: 'Москва' }, { value: '2', label: 'Тула' }]}
      error onRetry={vi.fn()} onChange={changed} />)
    await user.click(screen.getByRole('combobox', { name: 'Город' }))
    await user.click(screen.getByRole('option', { name: 'Тула' }))
    expect(changed).toHaveBeenCalledWith('2')
    await user.click(screen.getByRole('combobox', { name: 'Город' }))
    await user.keyboard('{ArrowUp}{Enter}')
    expect(changed).toHaveBeenCalledWith('')
  })

  it('references the popup only while it is mounted', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SearchableSelect label="Город" value="" options={[]} onChange={vi.fn()} />)
    const input = screen.getByRole('combobox', { name: 'Город' })
    expect(input).not.toHaveAttribute('aria-controls')
    await user.click(input)
    expect(document.getElementById(input.getAttribute('aria-controls')!)).toHaveAttribute('role', 'listbox')
    await user.keyboard('{Escape}')
    expect(input).not.toHaveAttribute('aria-controls')
  })

  it('announces the lookup error and allows an explicitly selected clear action', async () => {
    const user = userEvent.setup()
    const changed = vi.fn()
    renderWithProviders(<SearchableSelect label="Город" value="42" options={[]} error onRetry={vi.fn()} onChange={changed} />)
    const input = screen.getByRole('combobox', { name: 'Город' })
    expect(input).toHaveValue('Не удалось загрузить выбранное значение')
    await user.click(input)
    const error = screen.getByRole('alert')
    expect(input).toHaveAttribute('aria-describedby', error.id)
    await user.type(input, 'Новый')
    await user.keyboard('{Enter}')
    expect(changed).not.toHaveBeenCalled()
    await user.keyboard('{ArrowUp}{Enter}')
    expect(changed).toHaveBeenCalledWith('')
  })
})
