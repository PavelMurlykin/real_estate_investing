import { InteractiveTable } from '@/shared/ui/InteractiveTable'
import type { ReactNode, RefObject } from 'react'
import { useState } from 'react'

import type { TrenchMortgageCalculationResponse } from '@/api/schemas'
import { LoanParameters, SummaryItem } from './LoanParameters'
import {
  formatCurrency,
  formatDate,
  formatMonths,
  formatPercent,
} from '@/shared/lib/formatters'

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
          <LoanParameters assumptions={result.assumptions} paymentsCount={result.summary.paymentsCount} />
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
          <InteractiveTable rows={result.trenches} getRowKey={(trench) => trench.number}
              caption={`Рассчитанные параметры траншей`} className="property-table mortgage-schedule trench-table"
              columns={[
                { id: 'column0', label: "№", value: (trench) => trench.number, render: (trench) => <>{trench.number}</> },
                { id: 'column1', label: "Дата", value: (trench) => trench.date, searchValue: (trench) => formatDate(trench.date), render: (trench) => <>{formatDate(trench.date)}</> },
                { id: 'column2', label: "Доля", value: (trench) => Number(trench.percent), searchValue: (trench) => formatPercent(trench.percent), render: (trench) => <>{formatPercent(trench.percent)}</> },
                { id: 'column3', label: "Сумма", value: (trench) => Number(trench.amount), render: (trench) => <><strong>{formatCurrency(trench.amount)}</strong></> },
                { id: 'column4', label: "Ставка", value: (trench) => Number(trench.annualRate), searchValue: (trench) => formatPercent(trench.annualRate), render: (trench) => <>{formatPercent(trench.annualRate)}</> },
                { id: 'column5', label: "Платёж после выдачи", value: (trench) => Number(trench.monthlyPayment), searchValue: (trench) => formatCurrency(trench.monthlyPayment), render: (trench) => <>{formatCurrency(trench.monthlyPayment)}</> },
                { id: 'column6', label: "Платежей до следующего этапа", value: (trench) => trench.paymentsCount, render: (trench) => <>{trench.paymentsCount}</> },
                { id: 'column7', label: "Остаток к выдаче", value: (trench) => Number(trench.remainingDebt), searchValue: (trench) => formatCurrency(trench.remainingDebt), render: (trench) => <>{formatCurrency(trench.remainingDebt)}</> },
                { id: 'column8', label: "Переплата", value: (trench) => Number(trench.overpayment), searchValue: (trench) => formatCurrency(trench.overpayment), render: (trench) => <>{formatCurrency(trench.overpayment)}</> },
              ]} />
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
          <InteractiveTable rows={result.schedule} getRowKey={(payment) => payment.paymentNumber}
              caption={`Общий график ежемесячных платежей`} className="property-table mortgage-schedule" previewLimit={showFullSchedule ? undefined : 12}
              columns={[
                { id: 'column0', label: "№", value: (payment) => payment.paymentNumber, render: (payment) => <>{payment.paymentNumber}</> },
                { id: 'column1', label: "Дата", value: (payment) => payment.paymentDate, searchValue: (payment) => formatDate(payment.paymentDate), render: (payment) => <>{formatDate(payment.paymentDate)}</> },
                { id: 'column2', label: "Платёж", value: (payment) => Number(payment.paymentAmount), render: (payment) => <><strong>{formatCurrency(payment.paymentAmount)}</strong></> },
                { id: 'column3', label: "Проценты", value: (payment) => Number(payment.interestAmount), searchValue: (payment) => formatCurrency(payment.interestAmount), render: (payment) => <>{formatCurrency(payment.interestAmount)}</> },
                { id: 'column4', label: "Основной долг", value: (payment) => Number(payment.principalAmount), searchValue: (payment) => formatCurrency(payment.principalAmount), render: (payment) => <>{formatCurrency(payment.principalAmount)}</> },
                { id: 'column5', label: "Остаток", value: (payment) => Number(payment.remainingDebt), searchValue: (payment) => formatCurrency(payment.remainingDebt), render: (payment) => <>{formatCurrency(payment.remainingDebt)}</> },
              ]} />
        </div>
      </section>
    </div>
  )
}
