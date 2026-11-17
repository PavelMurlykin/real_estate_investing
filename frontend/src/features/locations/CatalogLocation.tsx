export function CatalogLocation({ location }: { location: { city: string; district?: string; region?: string } }) {
  const context = [...new Set([location.district, location.region].filter((value) => value && value !== location.city))].join(' · ')
  return <span>{location.city || 'Не уточнён'}{context ? <small className="field-hint"> · {context}</small> : null}</span>
}
