import { useId } from 'react'

import type { KeyRateChartPoint } from '@/api/schemas'
import { formatDate, formatPercent } from '@/shared/lib/formatters'

const left = 57
const right = 618
const top = 20
const bottom = 191

export function KeyRateChart({ history }: { history: KeyRateChartPoint[] }) {
  const titleId = useId()
  const descriptionId = useId()
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
  const timeSpan = latest.time - first.time
  const x = (time: number) => timeSpan
    ? left + ((time - first.time) / timeSpan) * (right - left)
    : (left + right) / 2
  const y = (rate: number) => bottom - ((rate - lowerRate) / rateSpan) * (bottom - top)
  const path = points.slice(1).map((point) => `H ${x(point.time)} V ${y(point.rate)}`).join(' ')
  const firstYear = Number(first.date.slice(0, 4))
  const latestYear = Number(latest.date.slice(0, 4))
  const yearStep = Math.max(1, Math.ceil((latestYear - firstYear) / 5))
  const yearTicks = Array.from(
    { length: Math.floor((latestYear - firstYear) / yearStep) + 1 },
    (_, index) => latestYear - index * yearStep,
  ).filter((year) => Date.UTC(year, 0, 1) >= first.time)
  const highlights = [
    { label: 'Минимум', point: minimum, kind: 'minimum' },
    { label: 'Максимум', point: maximum, kind: 'maximum' },
    { label: 'Последняя запись', point: latest, kind: 'latest' },
  ]

  return (
    <figure className="key-rate-chart">
      <figcaption id={titleId}>Динамика ключевой ставки</figcaption>
      <svg viewBox="0 0 640 232" role="img" aria-labelledby={titleId} aria-describedby={descriptionId}>
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
        {yearTicks.map((year, index) => (
          <text
            className={index % 2 === 1 ? 'key-rate-chart__minor-tick' : undefined}
            key={year}
            x={x(Date.UTC(year, 0, 1))}
            y={220}
            textAnchor="middle"
          >
            {year}
          </text>
        ))}
        {yearTicks.length === 0 ? (
          <text x={(left + right) / 2} y={220} textAnchor="middle">{latestYear}</text>
        ) : null}
        <path className="key-rate-chart__line" d={`M ${x(first.time)} ${y(first.rate)} ${path}`} />
        {points.map((point) => (
          <circle className="key-rate-chart__point" key={point.date} cx={x(point.time)} cy={y(point.rate)} r={3}>
            <title>{formatDate(point.date)} · {formatPercent(String(point.rate))}</title>
          </circle>
        ))}
        {highlights.map(({ point, kind }) => (
          <circle
            className={`key-rate-chart__marker key-rate-chart__marker--${kind}`}
            key={kind}
            cx={x(point.time)}
            cy={y(point.rate)}
            r={6}
          />
        ))}
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
