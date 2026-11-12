import { vi } from 'vitest'

import type { CatalogOption, PropertyListItem } from '@/api/schemas'

/** Keep catalog requests independent of calculation and saving mocks. */
export function mockMortgageCatalogs(properties: PropertyListItem[]) {
  const originalFetch = globalThis.fetch
  vi.stubGlobal('fetch', (async (path, options) => {
    const url = new URL(String(path), 'http://localhost')
    const dictionary = url.pathname.match(/\/catalog-options\/([^/]+)\//)?.[1]
    if (!dictionary) return originalFetch(path, options)
    const choices = properties.flatMap((property) => {
      const metadata = {
        regionId: property.regionId ?? 1, cityId: property.cityId ?? 1,
        districtId: property.districtId ?? 1, developerId: property.developerId ?? 1,
        realEstateComplexId: property.realEstateComplexId ?? 1,
      }
      const entries: Record<string, CatalogOption> = {
        regions: { ...metadata, id: metadata.regionId, label: `Регион ${metadata.regionId}` },
        cities: { ...metadata, id: metadata.cityId, label: property.city },
        districts: { ...metadata, id: metadata.districtId, label: property.district ?? 'Центральный' },
        developers: { ...metadata, id: metadata.developerId, label: property.developer },
        complexes: { ...metadata, id: metadata.realEstateComplexId, label: property.realEstateComplex },
        buildings: { ...metadata, id: property.buildingId ?? 1, label: property.building },
        layouts: { id: property.layoutId ?? 1, label: property.layout },
        decorations: { id: property.decorationId ?? 1, label: property.decoration },
      }
      return entries[dictionary] ? [entries[dictionary]] : []
    })
    const entries = [...new Map(choices.map((choice) => [choice.id, choice])).values()]
    const query = url.searchParams.get('q')?.toLocaleLowerCase('ru-RU') ?? ''
    return Response.json({
      page: 1, nextPage: null, totalCount: entries.length,
      results: entries.filter((entry) => entry.label.toLocaleLowerCase('ru-RU').includes(query)),
      selected: entries.filter((entry) => url.searchParams.getAll('selectedIds').includes(String(entry.id))),
    })
  }) as typeof fetch)
}
