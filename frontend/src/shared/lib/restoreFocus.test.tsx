import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '@/test/render'
import { restoreFocus } from './restoreFocus'

describe('restoreFocus', () => {
  it.each(['removed', 'disabled', 'hidden'])('returns to the list heading when the trigger is %s', (state) => {
    renderWithProviders(<main><h1>Список банков</h1><button disabled={state === 'disabled'} hidden={state === 'hidden'}>Удалить</button></main>)
    const trigger = screen.getByText('Удалить')
    if (state === 'removed') trigger.remove()
    restoreFocus(trigger)
    expect(screen.getByRole('heading')).toHaveFocus()
    expect(screen.getByRole('heading')).toHaveAttribute('tabindex', '-1')
  })

  it('returns to an available trigger without adding it to the tab order', () => {
    renderWithProviders(<main><h1>Список</h1><button>Удалить</button></main>)
    const trigger = screen.getByRole('button')
    restoreFocus(trigger)
    expect(trigger).toHaveFocus()
    expect(screen.getByRole('heading')).not.toHaveAttribute('tabindex')
  })
})
