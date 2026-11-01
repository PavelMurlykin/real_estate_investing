export function CalculationLayout({ url }: { url?: string }) {
  if (!url) return null
  return (
    <figure className="calculation-layout">
      <a href={url} target="_blank" rel="noreferrer" aria-label="Открыть планировку в полном размере">
        <img src={url} alt="Планировка квартиры" loading="lazy" />
      </a>
      <figcaption>Планировка квартиры</figcaption>
    </figure>
  )
}
