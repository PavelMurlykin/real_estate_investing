import { z } from 'zod'

export const geographicLocationSchema = z.object({
  id: z.number().int().positive(), label: z.string(), name: z.string(),
  type: z.string(), category: z.string(), parentId: z.number().nullable(),
  regionId: z.number().nullable(), parent: z.string().nullable(), region: z.string().nullable(),
  needsReview: z.boolean(), isActive: z.boolean(),
})
export const geographicPageSchema = z.object({
  results: z.array(geographicLocationSchema), totalCount: z.number(), nextPage: z.number().nullable(),
})
export const complexLocationsSchema = z.object({
  locations: z.array(geographicLocationSchema.extend({ isPrimary: z.boolean() })),
  buildings: z.array(z.object({
    id: z.number(), number: z.string(), locationId: z.number().nullable(), effectiveLocationId: z.number().nullable(),
  })),
})
export type ComplexLocations = z.infer<typeof complexLocationsSchema>
