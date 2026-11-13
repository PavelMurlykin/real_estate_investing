import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useRef, useState } from 'react'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '@/test/render'
import { Notice } from './Notice'

function SavedNotice() {
  const trigger = useRef<HTMLButtonElement>(null)
  const [saved, setSaved] = useState(false)
  return <form onSubmit={(event) => event.preventDefault()}>
    <button ref={trigger} type="button" onClick={() => setSaved(true)}>Сохранить</button>
    {saved ? <Notice tone="success" onDismiss={() => setSaved(false)} returnFocusRef={trigger}>Сохранено.</Notice> : null}
  </form>
}

describe('Notice', () => {
  it.each(['info', 'success', 'warning', 'error'] as const)('announces %s with the appropriate urgency without taking focus', (tone) => {
    renderWithProviders(<><button autoFocus>Продолжить</button><Notice tone={tone}>Сообщение</Notice></>)
    const notice = screen.getByRole(tone === 'error' ? 'alert' : 'status')
    expect(notice).toHaveTextContent('Сообщение')
    expect(notice).toHaveAttribute('aria-atomic', 'true')
    expect(screen.getByRole('button', { name: 'Продолжить' })).toHaveFocus()
    expect(within(notice).queryByRole('button')).not.toBeInTheDocument()
  })

  it('dismisses only on request, restores focus and shows a later result again', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SavedNotice />)
    const trigger = screen.getByRole('button', { name: 'Сохранить' })
    await user.click(trigger)
    expect(trigger).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Закрыть уведомление' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('status')).toHaveTextContent('Сохранено.')
  })
})
