import { act, fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { lazy } from 'react'
import { Link, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { AppShell } from './AppShell'

function mockViewport(initialMobile: boolean) {
  const listeners = new Set<() => void>()
  let isMobile = initialMobile
  vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
    get matches() { return query === '(max-width: 960px)' && isMobile },
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: (_event: string, listener: EventListenerOrEventListenerObject) => {
      if (query === '(max-width: 960px)') listeners.add(listener as () => void)
    },
    removeEventListener: (_event: string, listener: EventListenerOrEventListenerObject) => {
      listeners.delete(listener as () => void)
    },
    dispatchEvent: () => true,
  }))
  return (nextMobile: boolean) => act(() => {
    isMobile = nextMobile
    listeners.forEach((listener) => listener())
  })
}

function shellRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<h1>Главная страница</h1>} />
        <Route path="banks" element={(
          <>
            <h1>Банки</h1>
            <Link to="/banks?q=test">Фильтр банков</Link>
          </>
        )} />
      </Route>
    </Routes>
  )
}

beforeEach(() => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  // jsdom has no native modal focus handling; real-browser checks cover it.
  let opener: Element | null = null
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: {
      configurable: true,
      value: function (this: HTMLDialogElement) {
        opener = document.activeElement
        this.setAttribute('open', '')
        this.querySelector<HTMLButtonElement>('button')?.focus()
      },
    },
    close: {
      configurable: true,
      value: function (this: HTMLDialogElement) {
        this.removeAttribute('open')
        if (opener instanceof HTMLElement) opener.focus()
      },
    },
  })
})

describe('AppShell', () => {
  it('opens the mobile dialog, handles Escape and restores focus and scrolling', async () => {
    mockViewport(true)
    const user = userEvent.setup()
    document.body.style.overflow = 'auto'
    renderWithProviders(shellRoutes())
    const opener = screen.getByRole('button', { name: 'Открыть меню разделов' })
    expect(opener).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await user.click(opener)
    const dialog = screen.getByRole('dialog', { name: 'Навигация по разделам' })
    expect(opener).toHaveAttribute('aria-expanded', 'true')
    expect(within(dialog).getByRole('button', { name: 'Закрыть меню' })).toHaveFocus()
    expect(document.body.style.overflow).toBe('hidden')

    fireEvent(dialog, new Event('cancel', { cancelable: true }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveAttribute('aria-expanded', 'false')
    expect(opener).toHaveFocus()
    expect(document.body.style.overflow).toBe('auto')
    document.body.style.overflow = ''
  })

  it('closes on navigation and focuses content without disrupting query filters', async () => {
    mockViewport(true)
    const user = userEvent.setup()
    renderWithProviders(shellRoutes())
    await user.click(screen.getByRole('button', { name: 'Открыть меню разделов' }))
    await user.click(screen.getByRole('link', { name: 'Банки' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Банки' })).toBeInTheDocument()
    expect(screen.getByRole('main')).toHaveFocus()
    expect(window.scrollTo).toHaveBeenCalledTimes(1)
    expect(document.body.style.overflow).toBe('')

    const filter = screen.getByRole('link', { name: 'Фильтр банков' })
    await user.click(filter)
    expect(filter).toHaveFocus()
    expect(window.scrollTo).toHaveBeenCalledTimes(1)
  })

  it('closes on a backdrop click and switches to desktop without a stale modal', async () => {
    const resize = mockViewport(true)
    const user = userEvent.setup()
    renderWithProviders(shellRoutes())
    const opener = screen.getByRole('button', { name: 'Открыть меню разделов' })
    await user.click(opener)
    fireEvent.click(screen.getByRole('dialog'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()

    await user.click(opener)
    resize(false)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('complementary')).toBeInTheDocument()
    expect(document.body.style.overflow).toBe('')

    resize(true)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveAttribute('aria-expanded', 'false')
  })

  it('keeps navigation available while a route module is loading', async () => {
    mockViewport(false)
    let finishLoading!: (value: { default: () => React.JSX.Element }) => void
    const LazyPage = lazy(() => new Promise<{ default: () => React.JSX.Element }>((resolve) => {
      finishLoading = resolve
    }))
    renderWithProviders(
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<LazyPage />} />
        </Route>
      </Routes>,
    )
    expect(screen.getByRole('status', { name: 'Загрузка данных' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Основная навигация' })).toBeVisible()
    expect(screen.getByRole('navigation', { name: 'Разделы приложения' })).toBeVisible()

    await act(async () => finishLoading({ default: () => <h1>Страница загружена</h1> }))
    expect(await screen.findByRole('heading', { name: 'Страница загружена' }))
      .toBeInTheDocument()
  })

  it('contains page errors and recovers when another route is selected', async () => {
    mockViewport(false)
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const user = userEvent.setup()
    function BrokenPage(): never {
      throw new Error('Internal diagnostic that must not appear in the UI')
    }
    renderWithProviders(
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<BrokenPage />} />
          <Route path="banks" element={<h1>Банки</h1>} />
        </Route>
      </Routes>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Не удалось открыть страницу')
    expect(screen.queryByText(/Internal diagnostic/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Обновить страницу' })).toBeEnabled()
    await user.click(screen.getByRole('link', { name: 'Банки' }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Банки' })).toBeInTheDocument()
  })
})
