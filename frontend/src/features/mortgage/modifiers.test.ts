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
    localStorage.setItem(mortgageModifiersStorageKey, '{"amount":25000,"percent":0.01}')
    expect(loadMortgageModifiers()).toEqual({ amount: 25000, percent: 0.01 })
  })

  it('works when browser storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Storage blocked') })
    expect(loadMortgageModifiers()).toEqual(defaultMortgageModifiers)
  })
})
