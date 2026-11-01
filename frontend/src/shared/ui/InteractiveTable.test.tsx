import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { formatCurrency, formatDate } from '@/shared/lib/formatters'
import { renderWithProviders } from '@/test/render'

import { InteractiveTable } from './InteractiveTable'

describe('InteractiveTable', () => {
  it('sorts numbers across all rows and searches formatted values beyond the preview', async () => {
    const user = userEvent.setup()
    const rows = [
      { id: 1, amount: 9.15, date: '2026-03-01' },
      { id: 2, amount: 100.25, date: '2026-01-15' },
      { id: 3, amount: 20.05, date: '2026-02-01' },
    ]
    renderWithProviders(<InteractiveTable caption="Платежи" rows={rows} getRowKey={(row) => row.id} previewLimit={1} columns={[
      { id: 'date', label: 'Дата', value: (row) => row.date, searchValue: (row) => formatDate(row.date), render: (row) => formatDate(row.date) },
      { id: 'amount', label: 'Сумма', value: (row) => row.amount, render: (row) => formatCurrency(String(row.amount)) },
    ]} />)
    const table = screen.getByRole('table', { name: 'Платежи' })
    expect(within(table).getByText('9,15 ₽')).toBeInTheDocument()
    await user.click(within(table).getByRole('button', { name: 'Сумма' }))
    await user.keyboard('{Enter}')
    expect(within(table).getByText('100,25 ₽')).toBeInTheDocument()
    const search = screen.getByLabelText('Поиск в таблице: Платежи')
    await user.type(search, '01.02.2026')
    expect(within(table).getByText('20,05 ₽')).toBeInTheDocument()
    await user.clear(search)
    await user.type(search, '9,15')
    expect(within(table).getByText('9,15 ₽')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Найдено строк: 1')
  })
})
