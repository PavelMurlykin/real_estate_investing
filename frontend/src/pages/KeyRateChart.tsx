import { useCallback, useId, useState } from 'react'

import type { KeyRateChartPoint } from '@/api/schemas'
import { formatDate, formatPercent } from '@/shared/lib/formatters'

const left = 54
const rightMargin = 24
const top = 16
const shortestYearInMilliseconds = 365 * 24 * 60 * 60 * 1000
const minimumYearLabelSpacing = 44

export function KeyRateChart({ history }: { history: KeyRateChartPoint[] }) {
  const titleId = useId()
  const descriptionId = useId()
  const [width, setWidth] = useState(640)
  const observeChartWidth = useCallback((chart: SVGSVGElement | null) => {
    if (!chart || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) setWidth(entry.contentRect.width)
    })
    observer.observe(chart)
    return () => observer.disconnect()
  }, [])
  const points = history.map(({ meetingDate, keyRate }) => ({
    date: meetingDate,
    time: Date.parse(meetingDate),
    rate: Number(keyRate),
  }))
  const first = points[0]
  const latest = points[points.length - 1]
  if (!first || !latest) return null

  const minimum = points.reduce((lowest, point) => point.rate < lowest.rate ? point : lowest)
  const maximum = points.reduce((highest, point) => point.rate > highest.rate ? point : highest)
  const step = Math.max(1, Math.ceil((Math.ceil(maximum.rate) - Math.floor(minimum.rate)) / 4))
  const lowerRate = Math.floor(minimum.rate / step) * step
  const ticks = Array.from({ length: 6 }, (_, index) => lowerRate + index * step)
  const rateSpan = ticks[ticks.length - 1] - lowerRate
  // The original 800px card had 750px of space for the 640:232 plot.
  const height = Math.min(272, Math.max(144, Math.round(width * 232 / 640)))
  const bottom = height - 34
  const plotWidth = Math.max(1, width - left - rightMargin)
  const right = left + plotWidth
  const timeSpan = latest.time - first.time
  const x = (time: number) => timeSpan
    ? left + ((time - first.time) / timeSpan) * plotWidth
    : (left + right) / 2
  const y = (rate: number) => bottom - ((rate - lowerRate) / rateSpan) * (bottom - top)
  const path = points.slice(1).map((point) => `H ${x(point.time)} V ${y(point.rate)}`).join(' ')
  const firstYear = Number(first.date.slice(0, 4))
  const latestYear = Number(latest.date.slice(0, 4))
  const yearsSpanned = timeSpan / shortestYearInMilliseconds
  const labelIntervals = plotWidth / minimumYearLabelSpacing
  const yearStep = Math.max(1, Math.ceil(yearsSpanned / labelIntervals))
  const tickCount = Math.floor((latestYear - firstYear) / yearStep) + 1
  const yearTicks = Array.from({ length: tickCount }, (_, index) => (
    latestYear - (tickCount - 1 - index) * yearStep
  )).filter((year) => Date.UTC(year, 0, 1) >= first.time)
  const highlights = [
    { label: 'Минимум', point: minimum, kind: 'minimum' },
    { label: 'Максимум', point: maximum, kind: 'maximum' },
    { label: 'Последняя запись', point: latest, kind: 'latest' },
  ]
  const highlightKinds = new Map(highlights.map(({ point, kind }) => [point.date, kind]))

  return (
    <figure className="key-rate-chart">
      <figcaption id={titleId}>Динамика ключевой ставки</figcaption>
      <svg
        ref={observeChartWidth}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
      >
        <desc id={descriptionId}>
          Ключевая ставка в процентах годовых. Ступени показывают даты изменения ставки,
          точки отмечают записи в истории. Значения приведены в таблице ниже.
        </desc>
        {ticks.map((rate) => (
          <g key={rate}>
            <line className="key-rate-chart__grid" x1={left} x2={right} y1={y(rate)} y2={y(rate)} />
            <text x={left - 8} y={y(rate)} dy="0.35em" textAnchor="end">
              {formatPercent(String(rate))}
            </text>
          </g>
        ))}
        {yearTicks.map((year) => (
          <text
            className="key-rate-chart__year"
            key={year}
            x={x(Date.UTC(year, 0, 1))}
            y={height - 7}
            textAnchor="middle"
          >
            {year}
          </text>
        ))}
        {yearTicks.length === 0 ? (
          <text className="key-rate-chart__year" x={(left + right) / 2} y={height - 7} textAnchor="middle">
            {latestYear}
          </text>
        ) : null}
        <path className="key-rate-chart__line" d={`M ${x(first.time)} ${y(first.rate)} ${path}`} />
        {points.map((point) => {
          const kind = highlightKinds.get(point.date)
          const markerClasses = kind ? ` key-rate-chart__marker key-rate-chart__marker--${kind}` : ''
          return (
            <circle
              className={`key-rate-chart__point${markerClasses}`}
              key={point.date}
              cx={x(point.time)}
              cy={y(point.rate)}
              r={kind ? 6 : 3}
            >
              <title>{formatDate(point.date)} · {formatPercent(String(point.rate))}</title>
            </circle>
          )
        })}
      </svg>
      <ul className="key-rate-chart__legend">
        {highlights.map(({ label, point, kind }) => (
          <li key={kind}>
            <span className={`key-rate-chart__marker key-rate-chart__marker--${kind}`} aria-hidden="true" />
            <span>{label} <strong>{formatPercent(String(point.rate))}</strong> · {formatDate(point.date)}</span>
          </li>
        ))}
      </ul>
    </figure>
  )
}
