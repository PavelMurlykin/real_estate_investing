import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '@/test/render'
import { NavigationLink } from './NavigationLink'

describe('NavigationLink', () => {
  it.each([
    ['/banks/7/edit?q=test', '/banks', false, true],
    ['/banks/', '/banks', false, true],
    ['/banks-extra', '/banks', false, false],
    ['/mortgage/trench/calculations/7', '/mortgage', false, true],
    ['/mortgage-programs', '/mortgage', false, false],
    ['/mortgage/trench', '/mortgage', true, false],
    ['/', '/', true, true],
    ['/properties', '/', true, false],
  ] as const)('marks the correct section on %s for %s', (initialRoute, to, end, current) => {
    renderWithProviders(<NavigationLink to={to} label="Раздел" end={end} />, { initialRoute })
    const link = screen.getByRole('link', { name: 'Раздел' })
    if (current) expect(link).toHaveAttribute('aria-current', 'page')
    else expect(link).not.toHaveAttribute('aria-current')
  })

  it('honors aliases and excluded child paths', () => {
    renderWithProviders(<>
      <NavigationLink to="/customers" label="Клиенты" excludedPaths={['/customers/new']} />
      <NavigationLink to="/customers/new" label="Добавить" end />
      <NavigationLink to="/profile" label="Профиль" activePaths={['/password/change']} />
    </>, { initialRoute: '/customers/new' })
    expect(screen.getByRole('link', { name: 'Клиенты' })).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('link', { name: 'Добавить' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Профиль' })).not.toHaveAttribute('aria-current')
  })

  it('keeps the menu open for modified clicks and closes it for an ordinary click', () => {
    const onNavigate = vi.fn()
    renderWithProviders(<NavigationLink to="/banks" label="Банки" onNavigate={onNavigate} />)
    const link = screen.getByRole('link', { name: 'Банки' })
    const preventDocumentNavigation = (event: MouseEvent) => event.preventDefault()
    document.addEventListener('click', preventDocumentNavigation)
    try {
      for (const modifier of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }]) fireEvent.click(link, modifier)
    } finally { document.removeEventListener('click', preventDocumentNavigation) }
    expect(onNavigate).not.toHaveBeenCalled()
    fireEvent.click(link)
    expect(onNavigate).toHaveBeenCalledOnce()
  })
})
