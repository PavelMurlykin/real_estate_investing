import { afterEach, describe, expect, it, vi } from 'vitest'

import { defaultMortgageModifiers, loadMortgageModifiers, mortgageModifiersStorageKey } from './modifiers'

afterEach(() => localStorage.clear())

describe('mortgage modifiers', () => {
  it.each(['null', 'broken json', '[]', '{"amount":0,"percent":2}', '{"amount":1e100,"percent":"0.1"}'])(
    'falls back to the mobile defaults for invalid storage: %s', (stored) => {
      localStorage.setItem(mortgageModifiersStorageKey, stored)
      expect(loadMortgageModifiers()).toEqual(defaultMortgageModifiers)
    },
  )

  it('restores valid saved settings', () => {
    localStorage.setItem(mortgageModifiersStorageKey, '{"amount":25000,"smallAmount":500,"percent":0.01}')
    expect(loadMortgageModifiers()).toEqual({ amount: 25000, smallAmount: 500, percent: 0.01 })
  })

  it('preserves previous settings and adds the mobile default for small amounts', () => {
    localStorage.setItem(mortgageModifiersStorageKey, '{"amount":25000,"percent":0.01}')
    expect(loadMortgageModifiers()).toEqual({ amount: 25000, smallAmount: 10000, percent: 0.01 })
  })

  it.each([0, -1, 0.5, 1e100, '500'])('falls back for invalid small increments: %s', (smallAmount) => {
    localStorage.setItem(mortgageModifiersStorageKey, JSON.stringify({ amount: 20000, smallAmount, percent: 1 }))
    expect(loadMortgageModifiers()).toEqual({ amount: 20000, smallAmount: 10000, percent: 1 })
  })

  it('works when browser storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Storage blocked') })
    expect(loadMortgageModifiers()).toEqual(defaultMortgageModifiers)
  })
})
