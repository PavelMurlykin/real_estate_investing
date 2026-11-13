import { InteractiveTable } from '@/shared/ui/InteractiveTable'
import type { ReactNode, RefObject } from 'react'
import { useState } from 'react'

import type { MortgageCalculationResponse } from '@/api/schemas'
import { LoanParameters, SummaryItem } from './LoanParameters'
import {
  formatCurrency,
  formatDate,
  formatMonths,
  formatPercent,
} from '@/shared/lib/formatters'

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
  const graceCount = result.summary.gracePaymentsCount ?? result.assumptions.gracePeriodTermMonths
  const debtAfterGrace = result.summary.loanAfterGrace
    ?? result.schedule[graceCount - 1]?.remainingDebt

  return (
    <div className="mortgage-result">
      <section className="mortgage-summary detail-card detail-card--flush" aria-labelledby="mortgage-result-title">
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
          <LoanParameters assumptions={result.assumptions} paymentsCount={result.summary.paymentsCount} />
          <SummaryItem label="Основных платежей">
            {result.summary.mainPaymentsCount ?? result.summary.paymentsCount - graceCount}
          </SummaryItem>
          {result.assumptions.hasGracePeriod ? (
            <>
              <SummaryItem label="Срок льготного периода, месяцев">{result.assumptions.gracePeriodTermMonths}</SummaryItem>
              <SummaryItem label="Ставка льготного периода">{formatPercent(result.assumptions.gracePeriodRate ?? '0')}</SummaryItem>
              <SummaryItem label="Льготных платежей">{graceCount}</SummaryItem>
              <SummaryItem label="Долг после льготного периода">{debtAfterGrace === undefined ? '—' : formatCurrency(debtAfterGrace)}</SummaryItem>
            </>
          ) : null}
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

      <section className="schedule-panel detail-card" aria-labelledby="schedule-title">
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
          <InteractiveTable rows={result.schedule} getRowKey={(payment) => payment.paymentNumber}
              caption={`График ежемесячных платежей`} className="property-table mortgage-schedule" previewLimit={showFullSchedule ? undefined : 12}
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
