import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useRef, useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '@/test/render'
import { EmptyState, ErrorState, PageLoadingState } from './AsyncState'
import { controlLabel, LoadingFocusContext, type LoadingFocusTarget } from '@/shared/lib/loadingFocus'
import { SearchableSelect } from './SearchableSelect'

describe('AsyncState', () => {
  it('restores a dictionary selection after loading without reopening its dropdown', async () => {
    const user = userEvent.setup()
    function Page() {
      const memory = useRef<LoadingFocusTarget | null>(null)
      const [loading, setLoading] = useState(false)
      const [value, setValue] = useState('')
      return <LoadingFocusContext.Provider value={memory}><main onFocusCapture={(event) => {
        const element = event.target
        memory.current = { element, pathname: window.location.pathname, main: element.closest('main'), label: controlLabel(element) }
      }}>{loading ? <PageLoadingState /> : <SearchableSelect label="Город" value={value}
        options={[{ value: '1', label: 'Казань' }]} onChange={(value) => {
          setValue(value); setLoading(true); window.setTimeout(() => setLoading(false), 70)
        }} />}</main></LoadingFocusContext.Provider>
    }
    renderWithProviders(<Page />)
    await user.click(screen.getByRole('combobox', { name: 'Город' }))
    await user.keyboard('{ArrowDown}{Enter}')
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Город' })).toHaveFocus())
    expect(screen.getByRole('combobox', { name: 'Город' })).toHaveValue('Казань')
    expect(screen.getByRole('combobox', { name: 'Город' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
  it('restores a field by its label after dependent data temporarily replaces the form', async () => {
    const user = userEvent.setup()
    function Page() {
      const memory = useRef<LoadingFocusTarget | null>(null)
      const [loading, setLoading] = useState(false)
      return <LoadingFocusContext.Provider value={memory}><main onFocusCapture={(event) => {
        const element = event.target
        memory.current = { element, pathname: window.location.pathname, main: element.closest('main'), label: controlLabel(element) }
      }}>{loading ? <PageLoadingState /> : <form><label>Город<input onChange={() => {
        setLoading(true); window.setTimeout(() => setLoading(false), 70)
      }} /></label></form>}</main></LoadingFocusContext.Provider>
    }
    renderWithProviders(<Page />)
    await user.type(screen.getByRole('textbox', { name: 'Город' }), 'М')
    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Город' })).toHaveFocus())
  })
  it('disables retries when the same resource is being reloaded from another section', async () => {
    const user = userEvent.setup()
    const retry = vi.fn()
    renderWithProviders(<ErrorState onRetry={retry} isRetrying />)
    expect(screen.getByRole('button', { name: 'Повторяем…' })).toBeDisabled()
    await user.tab()
    await user.keyboard('{Enter}')
    expect(retry).not.toHaveBeenCalled()
  })
  it.each([false, true])('waits for a delayed view commit before restoring focus (loading view %s)', async (loading) => {
    const user = userEvent.setup()
    function Page() {
      const [phase, setPhase] = useState('error')
      return <main>{phase === 'ready' ? <h1>Список банков</h1> : phase === 'loading' ? <PageLoadingState compact />
        : <ErrorState onRetry={async () => {
          if (loading) setPhase('loading')
          window.setTimeout(() => setPhase('ready'), 70)
        }} />}</main>
    }
    renderWithProviders(<Page />)
    await user.click(screen.getByRole('button', { name: 'Повторить' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Список банков' })).toHaveFocus())
  })
  it('announces loading without moving focus and keeps empty data distinct from failure', () => {
    renderWithProviders(<><button autoFocus>Меню</button><PageLoadingState /><EmptyState title="Банков пока нет" description="Добавьте первый банк." /></>)
    expect(screen.getByRole('status', { name: 'Загрузка данных' })).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('region', { name: 'Банков пока нет' })).toHaveAccessibleDescription('Добавьте первый банк.')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Меню' })).toHaveFocus()
  })

  it('prevents duplicate retry requests and restores the retry button after another failure', async () => {
    const user = userEvent.setup()
    let reject: (error: Error) => void = () => undefined
    const response = new Promise<void>((_, fail) => { reject = fail })
    const retry = vi.fn(() => response)
    renderWithProviders(<main><ErrorState onRetry={retry} /></main>)
    await user.tab()
    await user.keyboard('{Enter}{Enter}')
    const pending = screen.getByRole('button', { name: 'Повторяем…' })
    expect(pending).toBeDisabled()
    expect(pending).toHaveAttribute('aria-busy', 'true')
    expect(retry).toHaveBeenCalledTimes(1)
    await act(async () => reject(new Error('Offline')))
    const button = await screen.findByRole('button', { name: 'Повторить' })
    await waitFor(() => expect(button).toHaveFocus())
    expect(button).toBeEnabled()
  })

  it.each([false, true])('restores focus after recovery only if the user has not moved it (moved %s)', async (moved) => {
    const user = userEvent.setup()
    let complete: () => void = () => undefined
    const response = new Promise<void>((resolve) => { complete = resolve })
    function Page() {
      const [loaded, setLoaded] = useState(false)
      return <main><a href="#help">Справка</a>{loaded ? <h1>Список банков</h1> : <ErrorState onRetry={async () => { await response; setLoaded(true) }} />}</main>
    }
    renderWithProviders(<Page />)
    await user.click(screen.getByRole('button', { name: 'Повторить' }))
    if (moved) screen.getByRole('link').focus()
    await act(async () => complete())
    await waitFor(() => expect(moved ? screen.getByRole('link') : screen.getByRole('heading')).toHaveFocus())
  })

  it('uses native keyboard activation without submitting an enclosing form', async () => {
    const user = userEvent.setup()
    const submit = vi.fn((event) => event.preventDefault())
    const retry = vi.fn()
    renderWithProviders(<form onSubmit={submit}><ErrorState onRetry={retry} /></form>)
    await user.tab()
    await user.keyboard(' ')
    expect(retry).toHaveBeenCalledTimes(1)
    expect(submit).not.toHaveBeenCalled()
  })
})
