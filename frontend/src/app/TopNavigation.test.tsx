import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { TopNavigation } from './TopNavigation'

describe('TopNavigation', () => {
  it('keeps only catalog and calculator links in the top panel', () => {
    renderWithProviders(
      <TopNavigation
        onOpenSidebar={vi.fn()}
        theme="system"
        onCycleTheme={vi.fn()}
      />,
    )

    const navigation = screen.getByRole('navigation', {
      name: 'Основная навигация',
    })
    const links = navigation.querySelectorAll('a')

    expect(links).toHaveLength(2)
    expect(screen.queryByRole('link', { name: 'Главная' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', {
      name: 'RealtyFlow — на главную',
    })).toHaveAttribute(
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

  it('shows the current theme preference as an icon button', () => {
    const onCycleTheme = vi.fn()
    renderWithProviders(
      <TopNavigation
        onOpenSidebar={vi.fn()}
        theme="system"
        onCycleTheme={onCycleTheme}
      />,
    )

    const themeControl = screen.getByRole('button', {
      name: 'Тема: системная. Включить светлую тему',
    })
    expect(themeControl.querySelector('svg')).toBeInTheDocument()
    fireEvent.click(themeControl)
    expect(onCycleTheme).toHaveBeenCalledOnce()
  })
})
