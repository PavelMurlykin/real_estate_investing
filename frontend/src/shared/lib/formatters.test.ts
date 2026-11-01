import { describe, expect, it } from 'vitest'

import { formatCurrency } from './formatters'

describe('formatCurrency', () => {
  it.each([
    ['50577.51', '50 577,51 ₽'], ['0.01', '0,01 ₽'],
    ['1000000.00', '1 000 000,00 ₽'], ['-0.25', '-0,25 ₽'],
  ])('preserves kopecks in %s', (value, expected) => {
    expect(formatCurrency(value).replace(/\u00a0/g, ' ')).toBe(expected)
  })
})
