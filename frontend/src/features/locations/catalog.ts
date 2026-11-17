import { z } from 'zod'
import { geographicLocationSchema } from './geography'

export const locationCatalogEntrySchema = geographicLocationSchema.extend({
  typeId: z.number().int().positive(), sourceStatus: z.string(), sourceVersion: z.string(),
  identifiers: z.array(z.object({ provider: z.string(), value: z.string() })).optional(),
  aliases: z.array(z.string()).optional(),
})
export const locationCatalogPageSchema = z.object({
  results: z.array(locationCatalogEntrySchema), page: z.number(), totalCount: z.number(), totalPages: z.number(),
  types: z.array(z.object({ id: z.number(), name: z.string() })),
})
export type LocationCatalogEntry = z.infer<typeof locationCatalogEntrySchema>
export type LocationCatalogKey = 'regions' | 'localities' | 'districts'
export const locationCatalogTitles = { regions: 'Регионы', localities: 'Населённые пункты', districts: 'Административные районы' }
export const locationNavigation = [
  ...Object.entries(locationCatalogTitles).map(([key, label]) => ({ to: `/locations/${key}`, label })),
  { to: '/locations/metro', label: 'Метро' }, { to: '/locations/metro-lines', label: 'Линии метро' },
  { to: '/locations/metro-systems', label: 'Системы метро' },
]
