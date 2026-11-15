import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { NumberField } from './NumberField'

describe('NumberField', () => {
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
