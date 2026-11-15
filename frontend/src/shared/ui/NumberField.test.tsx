import { useState } from 'react'
import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NumberField } from './NumberField'

afterEach(() => vi.useRealTimers())

function HoldEditor({ increment = 10, maximum = '100' }: { increment?: number; maximum?: string }) {
  const [value, setValue] = useState('0')
  return <NumberField label="Сумма" value={value} onValueChange={setValue} increment={increment} min="0" max={maximum} />
}

describe('NumberField', () => {
  it('repeats the configured step while held and stops on release without an extra click', () => {
    vi.useFakeTimers()
    render(<HoldEditor increment={0.1} />)
    const plus = screen.getByRole('button', { name: 'Увеличить: Сумма' })
    fireEvent(plus, new MouseEvent('pointerdown', { bubbles: true, button: 0 }))
    expect(screen.getByRole('spinbutton')).toHaveValue(0.1)
    act(() => vi.advanceTimersByTime(399))
    expect(screen.getByRole('spinbutton')).toHaveValue(0.1)
    act(() => vi.advanceTimersByTime(1))
    expect(screen.getByRole('spinbutton')).toHaveValue(0.2)
    act(() => vi.advanceTimersByTime(100))
    expect(screen.getByRole('spinbutton')).toHaveValue(0.3)
    fireEvent.pointerUp(window)
    fireEvent.click(plus, { detail: 1 })
    act(() => vi.advanceTimersByTime(1000))
    expect(screen.getByRole('spinbutton')).toHaveValue(0.3)
    const minus = screen.getByRole('button', { name: 'Уменьшить: Сумма' })
    fireEvent(minus, new MouseEvent('pointerdown', { bubbles: true, button: 0 }))
    act(() => vi.advanceTimersByTime(400))
    act(() => vi.advanceTimersByTime(100))
    expect(screen.getByRole('spinbutton')).toHaveValue(0)
    act(() => vi.advanceTimersByTime(1000))
    expect(screen.getByRole('spinbutton')).toHaveValue(0)
    expect(minus).toBeDisabled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each(['cancel', 'leave', 'blur', 'window blur', 'hidden'])(
    'stops a held button after %s', (reason) => {
      vi.useFakeTimers()
      render(<HoldEditor />)
      const plus = screen.getByRole('button', { name: 'Увеличить: Сумма' })
      fireEvent(plus, new MouseEvent('pointerdown', { bubbles: true, button: 0 }))
      if (reason === 'cancel') fireEvent.pointerCancel(window)
      if (reason === 'leave') fireEvent.pointerLeave(plus)
      if (reason === 'blur') fireEvent.blur(plus)
      if (reason === 'window blur') fireEvent(window, new Event('blur'))
      if (reason === 'hidden') {
        vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
        fireEvent(document, new Event('visibilitychange'))
      }
      act(() => vi.advanceTimersByTime(1000))
      expect(screen.getByRole('spinbutton')).toHaveValue(10)
    },
  )

  it('supports keyboard holding and stops when the button unmounts', () => {
    vi.useFakeTimers()
    const { unmount } = render(<HoldEditor maximum="20" />)
    const plus = screen.getByRole('button', { name: 'Увеличить: Сумма' })
    fireEvent.keyDown(plus, { key: ' ', repeat: false })
    fireEvent.keyDown(plus, { key: ' ', repeat: true })
    expect(screen.getByRole('spinbutton')).toHaveValue(10)
    act(() => vi.advanceTimersByTime(400))
    expect(screen.getByRole('spinbutton')).toHaveValue(20)
    fireEvent.keyUp(plus, { key: ' ' })
    expect(vi.getTimerCount()).toBe(0)
    const minus = screen.getByRole('button', { name: 'Уменьшить: Сумма' })
    fireEvent.keyDown(minus, { key: 'Enter' })
    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('uses the same decimal increment for buttons and arrow keys without rounding drift', async () => {
    const user = userEvent.setup()
    function Editor() {
      const [value, setValue] = useState('1.15')
      return <NumberField label="Ставка" value={value} onValueChange={setValue} increment={0.1} min="0" max="2" step="0.01" />
    }
    render(<Editor />)
    const field = screen.getByRole('spinbutton', { name: 'Ставка' })
    await user.click(screen.getByRole('button', { name: 'Увеличить: Ставка' }))
    expect(field).toHaveValue(1.25)
    field.focus()
    await user.keyboard('{ArrowUp}{ArrowUp}{ArrowDown}')
    expect(field).toHaveValue(1.35)
    await user.clear(field)
    await user.keyboard('{ArrowDown}')
    expect(field).toHaveValue(0)
    expect(screen.getByRole('button', { name: 'Уменьшить: Ставка' })).toBeDisabled()
    await user.clear(field)
    await user.type(field, '1.99')
    await user.keyboard('{ArrowUp}')
    expect(field).toHaveValue(2)
    expect(screen.getByRole('button', { name: 'Увеличить: Ставка' })).toBeDisabled()
  })

  it('keeps a calculated read-only value unchanged', async () => {
    const user = userEvent.setup()
    render(<NumberField label="Остаток" value="100" onValueChange={() => { throw new Error('Read-only changed') }} readOnly />)
    expect(screen.getAllByRole('button').every((button) => button.hasAttribute('disabled'))).toBe(true)
    screen.getByRole('spinbutton').focus()
    await user.keyboard('{ArrowUp}{ArrowDown}')
    expect(screen.getByRole('spinbutton')).toHaveValue(100)
  })
})
