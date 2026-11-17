export function formatCalculationLocation(property: { city: string; district?: string; region?: string }) {
  return [...new Set([property.city, property.district, property.region].filter(Boolean))].join(' · ')
}
