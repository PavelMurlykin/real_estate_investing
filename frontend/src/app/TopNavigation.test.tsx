import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { TopNavigation } from './TopNavigation'

describe('TopNavigation', () => {
  it('keeps exactly the three primary product links in the top panel', () => {
    renderWithProviders(
      <TopNavigation
        onOpenSidebar={vi.fn()}
        theme="light"
        onToggleTheme={vi.fn()}
      />,
    )

    const navigation = screen.getByRole('navigation', {
      name: 'Основная навигация',
    })
    const links = navigation.querySelectorAll('a')

    expect(links).toHaveLength(3)
    expect(screen.getByRole('link', { name: 'Главная' })).toHaveAttribute(
      'href',
      '/',
    )
    expect(
      screen.getByRole('link', { name: 'Объекты недвижимости' }),
    ).toHaveAttribute('href', '/properties')
    expect(
      screen.getByRole('link', { name: 'Ипотечный калькулятор' }),
    ).toHaveAttribute('href', '/mortgage')
  })
})
