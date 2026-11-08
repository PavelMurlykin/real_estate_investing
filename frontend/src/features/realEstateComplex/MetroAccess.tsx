export function MetroLineStripe({ line, color }: { line: string; color: string }) {
  return <span className="metro-line-stripe" role="img"
    aria-label={`Линия ${line}`} title={line} style={{ backgroundColor: color }} />
}

export function TransportIcon({ mode }: { mode: string }) {
  const walking = /пеш/i.test(mode)
  const train = /электрич|поезд/i.test(mode)
  return (
    <span className="transport-icon" role="img" aria-label={mode} title={mode}>
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        {walking ? <>
          <circle cx="14" cy="4" r="2" />
          <path d="m7 12 4-4 4 2 4 1M11 8l-1 7-4 6m4-6 5 2 2 5" />
        </> : <>
          <rect x="5" y="3" width="14" height="16" rx="3" />
          <path d="M5 12h14M8 19l-2 3m10-3 2 3M8 7h8" />
          <circle cx="8" cy="16" r=".7" /><circle cx="16" cy="16" r=".7" />
          {train ? <path d="M8 1h8" /> : null}
        </>}
      </svg>
    </span>
  )
}
