import { screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { Sidebar } from './Sidebar'

const authenticatedSession: Session = {
  isAuthenticated: true,
  user: {
    id: 1,
    displayName: 'Анна Иванова',
    email: 'anna@example.com',
    agencyName: 'Север',
  },
  capabilities: {
    manageCatalogs: false,
    syncExternalData: false,
    viewPrivateRecords: true,
    viewAllPrivateRecords: false,
  },
}

describe('Sidebar', () => {
  it('keeps private navigation hidden for anonymous visitors', () => {
    renderWithProviders(<Sidebar isOpen onClose={vi.fn()} />)

    const sidebar = screen.getByRole('complementary', {
      name: 'Навигация по разделам',
    })
    expect(within(sidebar).getByText('Недвижимость')).toBeInTheDocument()
    expect(within(sidebar).getByText('Справочники')).toBeInTheDocument()
    expect(
      within(sidebar).getByRole('link', { name: 'Группы компаний' }),
    ).toHaveAttribute('href', '/company-groups')
    expect(
      within(sidebar).getByRole('link', { name: 'Застройщики' }),
    ).toHaveAttribute('href', '/developers')
    expect(
      within(sidebar).getByRole('link', { name: 'Жилые комплексы' }),
    ).toHaveAttribute('href', '/complexes')
    expect(
      within(sidebar).getByRole('link', { name: 'Справочники объектов' }),
    ).toHaveAttribute('href', '/dictionaries/real-estate-types')
    expect(
      within(sidebar).getByRole('link', { name: 'Локации' }),
    ).toHaveAttribute('href', '/locations/regions')
    expect(
      within(sidebar).getByRole('link', { name: 'Банки' }),
    ).toHaveAttribute('href', '/banks')
    expect(
      within(sidebar).getByRole('link', { name: 'Ипотечные программы' }),
    ).toHaveAttribute('href', '/mortgage-programs')
    expect(
      within(sidebar).getByRole('link', { name: 'Программы застройщиков' }),
    ).toHaveAttribute('href', '/developer-programs')
    expect(
      within(sidebar).getByRole('link', { name: 'Ключевая ставка' }),
    ).toHaveAttribute('href', '/key-rate')
    expect(within(sidebar).queryByText('Клиенты')).not.toBeInTheDocument()
    expect(within(sidebar).getByRole('link', { name: 'Войти' })).toHaveAttribute(
      'href',
      '/login',
    )
  })

  it('shows private workflows and account actions for authenticated users', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], authenticatedSession)

    renderWithProviders(<Sidebar isOpen onClose={vi.fn()} />, { queryClient })

    expect(screen.getByText('Работа с клиентами')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Клиенты' })).toHaveAttribute(
      'href',
      '/customers',
    )
    expect(
      screen.getByRole('link', { name: 'Расчёты ипотеки' }),
    ).toHaveAttribute('href', '/mortgage/calculations')
    expect(
      screen.getByRole('link', { name: 'Траншевая ипотека' }),
    ).toHaveAttribute('href', '/mortgage/trench')
    expect(screen.getByText('Анна Иванова')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Выйти' })).toBeEnabled()
  })
})
