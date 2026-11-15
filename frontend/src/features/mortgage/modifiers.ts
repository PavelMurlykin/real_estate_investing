export const mortgageModifiersStorageKey = 'mortgage-calculator-modifiers'
export const percentIncrements = [1, 0.1, 0.01] as const
export type MortgageModifiers = { amount: number; percent: number }
export const defaultMortgageModifiers: MortgageModifiers = { amount: 100_000, percent: 0.1 }

export function isValidAmountIncrement(value: number) {
  return Number.isInteger(value) && value >= 1 && value <= 1_000_000_000
}

export function loadMortgageModifiers(): MortgageModifiers {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(mortgageModifiersStorageKey) ?? 'null')
    if (!stored || typeof stored !== 'object') return defaultMortgageModifiers
    const { amount, percent } = stored as Record<string, unknown>
    return {
      amount: typeof amount === 'number' && isValidAmountIncrement(amount) ? amount : defaultMortgageModifiers.amount,
      percent: typeof percent === 'number' && percentIncrements.some((option) => option === percent)
        ? percent : defaultMortgageModifiers.percent,
    }
  } catch {
    return defaultMortgageModifiers
  }
}
