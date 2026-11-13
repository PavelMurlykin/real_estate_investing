import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { Pagination } from './Pagination'

describe('Pagination', () => {
  it('announces the current page and supports keyboard navigation without submitting a form', async () => {
    const user = userEvent.setup()
    const change = vi.fn()
    const submit = vi.fn((event) => event.preventDefault())
    renderWithProviders(<form onSubmit={submit}><Pagination label="Страницы каталога" page={2} totalPages={3} onPageChange={change} /></form>)
    expect(screen.getByRole('navigation', { name: 'Страницы каталога' })).toHaveTextContent('Страница 2 из 3')
    await user.tab()
    await user.keyboard('{Enter}')
    expect(change).toHaveBeenLastCalledWith(1)
    await user.tab()
    await user.keyboard(' ')
    expect(change).toHaveBeenLastCalledWith(3)
    expect(submit).not.toHaveBeenCalled()
  })

  it.each([1, 3])('disables navigation beyond page boundaries at page %s', (page) => {
    renderWithProviders(<Pagination label="Страницы" page={page} totalPages={3} onPageChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Назад' })).toHaveProperty('disabled', page === 1)
    expect(screen.getByRole('button', { name: 'Далее' })).toHaveProperty('disabled', page === 3)
  })

  it('does not show empty pagination for a single page', () => {
    renderWithProviders(<Pagination label="Страницы" page={1} totalPages={1} onPageChange={vi.fn()} />)
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })
})
