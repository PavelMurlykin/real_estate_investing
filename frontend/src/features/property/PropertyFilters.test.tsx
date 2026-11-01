import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '@/test/render'
import { ResetFilters } from '@/shared/ui/ResetFilters'
import { PropertyFilters } from './PropertyFilters'

function Address() { return <output data-testid="address">{useLocation().search}</output> }

describe('PropertyFilters', () => {
  it('loads all reference filters automatically, clears only the chosen cascade and resets the full panel', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify({
      page: 1, nextPage: null, totalCount: 2, selected: [{ id: 1, label: 'Москва' }],
      results: [{ id: 1, label: 'Москва' }, { id: 2, label: 'Тула' }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<><PropertyFilters /><ResetFilters /><Address /></>, {
      initialRoute: '/?customerId=12&city=1&developer=2&realEstateComplex=3&building=4&layout=5&area=42.5&page=3',
    })
    await waitFor(() => expect(new Set(fetchMock.mock.calls.map(([path]) => new URL(String(path), 'http://localhost').pathname)).size).toBe(5))
    expect(screen.queryByRole('button', { name: /варианты/ })).not.toBeInTheDocument()
    expect(screen.getAllByRole('combobox')).toHaveLength(5)
    const city = screen.getByRole('combobox', { name: 'Город' })
    await waitFor(() => expect(city).toHaveValue('Москва'))
    await user.click(city)
    await user.click(screen.getByRole('option', { name: 'Все' }))
    const address = screen.getByTestId('address').textContent ?? ''
    const parameters = new URLSearchParams(address)
    expect(parameters.has('city')).toBe(false)
    expect(parameters.get('realEstateComplex')).toBe('3')
    expect(parameters.get('building')).toBe('4')
    expect(parameters.has('page')).toBe(false)
    expect(parameters.get('developer')).toBe('2')
    expect(parameters.get('layout')).toBe('5')
    expect(parameters.get('area')).toBe('42.5')
    expect(parameters.get('customerId')).toBe('12')
    await user.click(city)
    await user.click(await screen.findByRole('option', { name: 'Тула' }))
    const changed = new URLSearchParams(screen.getByTestId('address').textContent ?? '')
    expect(changed.get('city')).toBe('2')
    expect(changed.has('realEstateComplex')).toBe(false)
    expect(changed.has('building')).toBe(false)
    expect(changed.get('layout')).toBe('5')
    await user.click(screen.getByRole('button', { name: 'Сбросить' }))
    expect(screen.getByTestId('address')).toHaveTextContent('?customerId=12')
    expect(screen.getByLabelText('Площадь, м²')).toHaveValue(null)
  })
})
