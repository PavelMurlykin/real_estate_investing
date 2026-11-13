import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { ModalDialog } from './ModalDialog'

function Example({ remove = () => undefined }: { remove?: () => void }) {
  const [open, setOpen] = useState(false)
  const [pending, setPending] = useState(false)
  return <><button onClick={() => setOpen(true)}>Удалить запись</button><a href="/banks">К списку</a>
    {open ? <ModalDialog labelledBy="delete-title" describedBy="delete-description" pending={pending} onClose={() => setOpen(false)}>
      <h2 id="delete-title" tabIndex={-1}>Удалить?</h2><p id="delete-description">Запись исчезнет из списка.</p>
      <button disabled={pending} onClick={() => setOpen(false)}>Отмена</button>
      <button disabled={pending} onClick={() => { setPending(true); remove() }}>Подтвердить</button>
    </ModalDialog> : null}</>
}

describe('ModalDialog', () => {
  it('starts on the safe action, cycles focus in both directions and restores focus after Escape', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Example />)
    const trigger = screen.getByRole('button', { name: 'Удалить запись' })
    await user.click(trigger)
    const dialog = screen.getByRole('alertdialog', { name: 'Удалить?' })
    expect(dialog).toHaveAccessibleDescription('Запись исчезнет из списка.')
    const cancel = within(dialog).getByRole('button', { name: 'Отмена' })
    const confirm = within(dialog).getByRole('button', { name: 'Подтвердить' })
    expect(cancel).toHaveFocus()
    await user.tab({ shift: true })
    expect(confirm).toHaveFocus()
    await user.tab()
    expect(cancel).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
    expect(document.body.style.overflow).toBe('')
  })

  it('keeps pending work focused and prevents dismissal and duplicate confirmation', async () => {
    const user = userEvent.setup()
    const remove = vi.fn()
    renderWithProviders(<Example remove={remove} />)
    await user.click(screen.getByRole('button', { name: 'Удалить запись' }))
    const dialog = screen.getByRole('alertdialog')
    await user.click(within(dialog).getByRole('button', { name: 'Подтвердить' }))
    expect(within(dialog).getByRole('heading')).toHaveFocus()
    await user.tab()
    await user.keyboard('{Escape}{Enter}')
    fireEvent(dialog, new Event('cancel', { cancelable: true }))
    expect(dialog).toBeInTheDocument()
    expect(within(dialog).getByRole('heading')).toHaveFocus()
    expect(remove).toHaveBeenCalledTimes(1)
  })

  it('restores focus when cancel is activated with the keyboard', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Example />)
    const trigger = screen.getByRole('button', { name: 'Удалить запись' })
    await user.click(trigger)
    await user.keyboard('{Enter}')
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })
})
