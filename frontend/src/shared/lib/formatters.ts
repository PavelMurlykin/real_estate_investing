const currencyFormatter = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const decimalFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

const integerFormatter = new Intl.NumberFormat('ru-RU')

const dateFormatter = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

const dateTimeFormatter = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatCurrency(value: string): string {
  return currencyFormatter.format(Number(value))
}

export function formatArea(value: string): string {
  return `${decimalFormatter.format(Number(value))} м²`
}

export function formatInteger(value: number): string {
  return integerFormatter.format(value)
}

export function formatPercent(value: string): string {
  return `${decimalFormatter.format(Number(value))}%`
}

export function formatDate(value: string): string {
  return dateFormatter.format(new Date(`${value}T00:00:00`))
}

export function formatDateTime(value: string): string {
  return dateTimeFormatter.format(new Date(value))
}

export function formatMonths(value: number): string {
  const years = Math.floor(value / 12)
  const months = value % 12
  if (years === 0) return `${months} мес.`
  if (months === 0) return `${years} г.`
  return `${years} г. ${months} мес.`
}
