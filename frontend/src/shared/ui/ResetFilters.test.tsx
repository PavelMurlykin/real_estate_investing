import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '@/test/render'
import { ResetFilters } from './ResetFilters'

function Address() { return <output data-testid="address">{useLocation().search}</output> }

describe('ResetFilters', () => {
  it('clears filters, ordering and pagination while retaining the customer context', async () => {
    const user = userEvent.setup()
    renderWithProviders(<><ResetFilters /><Address /></>, { initialRoute: '/?customerId=12&city=1&area=42.5&ordering=-area&page=3' })
    await user.click(screen.getByRole('button', { name: 'Сбросить' }))
    expect(screen.getByTestId('address')).toHaveTextContent('?customerId=12')
  })
  it('resets only the calculation filters on a customer page', async () => {
    const user = userEvent.setup()
    renderWithProviders(<><ResetFilters prefix="calculation" /><Address /></>, { initialRoute: '/?tab=budget&calculationCity=1&calculationPage=3&calculationOrdering=-annualRate' })
    await user.click(screen.getByRole('button', { name: 'Сбросить' }))
    expect(screen.getByTestId('address')).toHaveTextContent('?tab=budget')
  })
})
