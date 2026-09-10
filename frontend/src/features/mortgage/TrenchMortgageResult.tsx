import type { ReactNode, RefObject } from 'react'
import { useState } from 'react'

import type { TrenchMortgageCalculationResponse } from '@/api/schemas'
import {
  formatCurrency,
  formatDate,
  formatMonths,
  formatPercent,
} from '@/shared/lib/formatters'

function SummaryItem({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="mortgage-summary__item">
      <span>{label}</span>
      <strong>{children}</strong>
    </div>
  )
}

type TrenchMortgageResultProps = {
  result: TrenchMortgageCalculationResponse
  headingRef?: RefObject<HTMLHeadingElement | null>
  summaryAction?: ReactNode
}

export function TrenchMortgageResult({
  result,
  headingRef,
  summaryAction,
}: TrenchMortgageResultProps) {
  const [showFullSchedule, setShowFullSchedule] = useState(false)
  const visibleSchedule = showFullSchedule
    ? result.schedule
    : result.schedule.slice(0, 12)

  return (
    <div className="mortgage-result trench-mortgage-result">
      <section
        className="mortgage-summary"
        aria-labelledby="trench-mortgage-result-title"
      >
        <div className="mortgage-summary__heading">
          <div>
            <span className="eyebrow">Результат расчёта</span>
            <h2
              id="trench-mortgage-result-title"
              ref={headingRef}
              tabIndex={-1}
            >
              Параметры траншевого кредита
            </h2>
          </div>
          <span className="mortgage-summary__term">
            {formatMonths(result.assumptions.mortgageTermMonths)}
          </span>
        </div>
        <div className="mortgage-summary__primary">
          <span>Максимальный ежемесячный платёж</span>
          <strong>
            {formatCurrency(result.summary.maximumMonthlyPayment)}
          </strong>
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
          <SummaryItem label="Количество траншей">
            {result.assumptions.trenchCount}
          </SummaryItem>
        </div>
      </section>

      <section
        className="schedule-panel trench-summary-panel"
        aria-labelledby="trench-summary-title"
      >
        <div className="section-heading">
          <div>
            <span className="eyebrow">Этапы финансирования</span>
            <h2 id="trench-summary-title">Параметры траншей</h2>
          </div>
        </div>
        <div className="mortgage-schedule-wrapper">
          <table className="property-table mortgage-schedule trench-table">
            <caption className="visually-hidden">
              Рассчитанные параметры траншей
            </caption>
            <thead>
              <tr>
                <th scope="col">№</th>
                <th scope="col">Дата</th>
                <th scope="col">Доля</th>
                <th scope="col">Сумма</th>
                <th scope="col">Ставка</th>
                <th scope="col">Платёж после выдачи</th>
                <th scope="col">Платежей до следующего этапа</th>
                <th scope="col">Остаток к выдаче</th>
              </tr>
            </thead>
            <tbody>
              {result.trenches.map((trench) => (
                <tr key={trench.number}>
                  <td>{trench.number}</td>
                  <td>{formatDate(trench.date)}</td>
                  <td>{formatPercent(trench.percent)}</td>
                  <td><strong>{formatCurrency(trench.amount)}</strong></td>
                  <td>{formatPercent(trench.annualRate)}</td>
                  <td>{formatCurrency(trench.monthlyPayment)}</td>
                  <td>{trench.paymentsCount}</td>
                  <td>{formatCurrency(trench.remainingDebt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {summaryAction}

      <section className="schedule-panel" aria-labelledby="trench-schedule-title">
        <div className="section-heading section-heading--with-action">
          <div>
            <span className="eyebrow">Детализация</span>
            <h2 id="trench-schedule-title">Общий график платежей</h2>
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
            <caption className="visually-hidden">
              Общий график ежемесячных платежей
            </caption>
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
                  <td>
                    <strong>{formatCurrency(payment.paymentAmount)}</strong>
                  </td>
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
