import type { ReactNode } from 'react'

import type { MortgageCalculationResponse } from '@/api/schemas'
import { formatCurrency, formatDate, formatMonths, formatPercent } from '@/shared/lib/formatters'

export function SummaryItem({ label, children }: { label: string; children: ReactNode }) {
  return <div className="mortgage-summary__item"><span>{label}</span><strong>{children}</strong></div>
}

type LoanParametersProps = {
  assumptions: Pick<MortgageCalculationResponse['assumptions'],
    'basePropertyCost' | 'priceAdjustmentType' | 'priceAdjustmentPercent' | 'priceAdjustmentRubles' |
    'initialPaymentPercent' | 'initialPaymentDate' | 'mortgageTermMonths' | 'annualRate'>
  paymentsCount: number
}

export function LoanParameters({ assumptions, paymentsCount }: LoanParametersProps) {
  return (
    <>
      <SummaryItem label="Базовая стоимость">{formatCurrency(assumptions.basePropertyCost)}</SummaryItem>
      <SummaryItem label={assumptions.priceAdjustmentType === 'discount' ? 'Скидка' : 'Удорожание'}>
        {formatPercent(assumptions.priceAdjustmentPercent)} · {formatCurrency(assumptions.priceAdjustmentRubles)}
      </SummaryItem>
      <SummaryItem label="Первоначальный взнос, %">{formatPercent(assumptions.initialPaymentPercent)}</SummaryItem>
      <SummaryItem label="Дата первоначального взноса">{formatDate(assumptions.initialPaymentDate)}</SummaryItem>
      <SummaryItem label="Срок ипотеки, месяцев">
        {assumptions.mortgageTermMonths} ({formatMonths(assumptions.mortgageTermMonths)})
      </SummaryItem>
      <SummaryItem label="Количество платежей">{paymentsCount}</SummaryItem>
      <SummaryItem label="Годовая ставка">{formatPercent(assumptions.annualRate)}</SummaryItem>
    </>
  )
}
