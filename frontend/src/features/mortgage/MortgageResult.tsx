import type { ReactNode, RefObject } from 'react'
import { useState } from 'react'

import type { MortgageCalculationResponse } from '@/api/schemas'
import {
  formatCurrency,
  formatDate,
  formatMonths,
  formatPercent,
} from '@/shared/lib/formatters'

function SummaryItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="mortgage-summary__item">
      <span>{label}</span>
      <strong>{children}</strong>
    </div>
  )
}

type MortgageResultProps = {
  result: MortgageCalculationResponse
  headingRef?: RefObject<HTMLHeadingElement | null>
  summaryAction?: ReactNode
}

export function MortgageResult({
  result,
  headingRef,
  summaryAction,
}: MortgageResultProps) {
  const [showFullSchedule, setShowFullSchedule] = useState(false)
  const visibleSchedule = showFullSchedule
    ? result.schedule
    : result.schedule.slice(0, 12)

  return (
    <div className="mortgage-result">
      <section className="mortgage-summary" aria-labelledby="mortgage-result-title">
        <div className="mortgage-summary__heading">
          <div>
            <span className="eyebrow">Результат расчёта</span>
            <h2 id="mortgage-result-title" ref={headingRef} tabIndex={-1}>
              Параметры кредита
            </h2>
          </div>
          <span className="mortgage-summary__term">
            {formatMonths(result.assumptions.mortgageTermMonths)}
          </span>
        </div>
        <div className="mortgage-summary__primary">
          <span>Ежемесячный платёж</span>
          <strong>{formatCurrency(result.summary.mainMonthlyPayment)}</strong>
          <small>до {formatDate(result.summary.mortgageEndDate)}</small>
        </div>
        <div className="mortgage-summary__grid">
          <SummaryItem label="Стоимость после корректировки">
            {formatCurrency(result.assumptions.finalPropertyCost)}
          </SummaryItem>
          <SummaryItem label="Первоначальный взнос">
            {formatCurrency(result.assumptions.initialPaymentRubles)}
          </SummaryItem>
          <SummaryItem label="Сумма кредита">
            {formatCurrency(result.summary.loanAmount)}
          </SummaryItem>
          <SummaryItem label="Переплата">
            {formatCurrency(result.summary.overpayment)}
          </SummaryItem>
          <SummaryItem label="Всего выплат">
            {formatCurrency(result.summary.totalPayments)}
          </SummaryItem>
          <SummaryItem label="Годовая ставка">
            {formatPercent(result.assumptions.annualRate)}
          </SummaryItem>
        </div>
        {result.summary.graceMonthlyPayment ? (
          <div className="grace-result">
            Льготный платёж: <strong>
              {formatCurrency(result.summary.graceMonthlyPayment)}
            </strong>{' '}
            до {formatDate(result.summary.gracePeriodEndDate ?? '')}
          </div>
        ) : null}
      </section>

      {summaryAction}

      <section className="schedule-panel" aria-labelledby="schedule-title">
        <div className="section-heading section-heading--with-action">
          <div>
            <span className="eyebrow">Детализация</span>
            <h2 id="schedule-title">График платежей</h2>
          </div>
          {result.schedule.length > 12 ? (
            <button
              className="button button--secondary"
              type="button"
              onClick={() => setShowFullSchedule((current) => !current)}
            >
              {showFullSchedule ? 'Первые 12 платежей' : 'Показать весь график'}
            </button>
          ) : null}
        </div>
        <div className="mortgage-schedule-wrapper">
          <table className="property-table mortgage-schedule">
            <caption className="visually-hidden">График ежемесячных платежей</caption>
            <thead>
              <tr>
                <th scope="col">№</th>
                <th scope="col">Дата</th>
                <th scope="col">Платёж</th>
                <th scope="col">Проценты</th>
                <th scope="col">Основной долг</th>
                <th scope="col">Остаток</th>
              </tr>
            </thead>
            <tbody>
              {visibleSchedule.map((payment) => (
                <tr key={payment.paymentNumber}>
                  <td>{payment.paymentNumber}</td>
                  <td>{formatDate(payment.paymentDate)}</td>
                  <td><strong>{formatCurrency(payment.paymentAmount)}</strong></td>
                  <td>{formatCurrency(payment.interestAmount)}</td>
                  <td>{formatCurrency(payment.principalAmount)}</td>
                  <td>{formatCurrency(payment.remainingDebt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
