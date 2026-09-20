import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { useTheme } from './theme'

function ThemeHarness() {
  const { theme, resolvedTheme, cycleTheme } = useTheme()
  return (
    <button type="button" onClick={cycleTheme}>
      {theme}:{resolvedTheme}
    </button>
  )
}

function mockSystemTheme(initialDark: boolean) {
  const listeners = new Set<(event: MediaQueryListEvent) => void>()
  let isDark = initialDark
  vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
    get matches() {
      return query === '(prefers-color-scheme: dark)' && isDark
    },
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: (
      _event: string,
      listener: EventListenerOrEventListenerObject,
    ) => {
      listeners.add(listener as (event: MediaQueryListEvent) => void)
    },
    removeEventListener: (
      _event: string,
      listener: EventListenerOrEventListenerObject,
    ) => {
      listeners.delete(listener as (event: MediaQueryListEvent) => void)
    },
    dispatchEvent: () => true,
  }))
  return (nextDark: boolean) => act(() => {
    isDark = nextDark
    listeners.forEach((listener) => listener({ matches: isDark } as MediaQueryListEvent))
  })
}

beforeEach(() => {
  window.localStorage.clear()
  delete document.documentElement.dataset.theme
  document.documentElement.style.colorScheme = ''
})

describe('useTheme', () => {
  it('cycles through system, light and dark preferences', async () => {
    const setSystemDark = mockSystemTheme(true)
    const user = userEvent.setup()
    renderWithProviders(<ThemeHarness />)

    const control = screen.getByRole('button', { name: 'system:dark' })
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(window.localStorage.getItem('theme-preference')).toBe('system')

    await user.click(control)
    expect(control).toHaveAccessibleName('light:light')
    expect(window.localStorage.getItem('theme-preference')).toBe('light')

    await user.click(control)
    expect(control).toHaveAccessibleName('dark:dark')

    await user.click(control)
    expect(control).toHaveAccessibleName('system:dark')
    setSystemDark(false)
    expect(control).toHaveAccessibleName('system:light')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('restores an explicit saved preference', () => {
    mockSystemTheme(false)
    window.localStorage.setItem('theme-preference', 'dark')
    renderWithProviders(<ThemeHarness />)

    expect(screen.getByRole('button', { name: 'dark:dark' })).toBeInTheDocument()
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
