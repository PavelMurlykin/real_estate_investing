import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { SortableHeader } from './SortableHeader'

function Table({ namespaced = false }: { namespaced?: boolean }) {
  const location = useLocation()
  return <><table><thead><tr>
    <SortableHeader field="area" parameter={namespaced ? 'calculationOrdering' : 'ordering'}
      pageParameter={namespaced ? 'calculationPage' : 'page'}>Площадь</SortableHeader>
  </tr></thead><tbody /></table><output aria-label="Адрес">{location.search}</output></>
}

describe('SortableHeader', () => {
  it.each([false, true])('toggles direction, resets only its page and preserves filters (namespace %s)', async (namespaced) => {
    const user = userEvent.setup()
    renderWithProviders(<Table namespaced={namespaced} />, { initialRoute: '/?q=Казань&page=4&calculationPage=3&customerId=12' })
    const header = screen.getByRole('columnheader', { name: 'Площадь' })
    expect(header).toHaveAttribute('aria-sort', 'none')
    await user.click(screen.getByRole('button', { name: 'Площадь' }))
    expect(header).toHaveAttribute('aria-sort', 'ascending')
    const parameters = new URLSearchParams(screen.getByLabelText('Адрес').textContent ?? '')
    expect(parameters.get(namespaced ? 'calculationOrdering' : 'ordering')).toBe('area')
    expect(parameters.has(namespaced ? 'calculationPage' : 'page')).toBe(false)
    expect(parameters.get(namespaced ? 'page' : 'calculationPage')).toBe(namespaced ? '4' : '3')
    expect(parameters.get('customerId')).toBe('12')
    expect(parameters.get('q')).toBe('Казань')
    await user.keyboard('{Enter}')
    expect(header).toHaveAttribute('aria-sort', 'descending')
  })
})
