import { z } from 'zod'

export const capabilitiesSchema = z.object({
  manageCatalogs: z.boolean(),
  syncExternalData: z.boolean(),
  viewPrivateRecords: z.boolean(),
  viewAllPrivateRecords: z.boolean(),
})

export const sessionSchema = z.object({
  isAuthenticated: z.boolean(),
  user: z
    .object({
      id: z.number().int().positive(),
      displayName: z.string(),
      email: z.string(),
      agencyName: z.string(),
    })
    .nullable(),
  capabilities: capabilitiesSchema,
})

export const propertyListItemSchema = z.object({
  id: z.number().int().positive(),
  city: z.string(),
  developer: z.string(),
  realEstateComplex: z.string(),
  building: z.string(),
  apartmentNumber: z.string(),
  layout: z.string(),
  decoration: z.string(),
  area: z.string(),
  floor: z.number().int(),
  propertyCost: z.string(),
  detailUrl: z.string(),
})

export const propertyListResponseSchema = z.object({
  page: z.number().int().positive(),
  pageSize: z.number().int().positive(),
  totalCount: z.number().int().nonnegative(),
  totalPages: z.number().int().nonnegative(),
  results: z.array(propertyListItemSchema),
})

export const overviewSchema = z.object({
  statistics: z.array(
    z.object({
      key: z.string(),
      label: z.string(),
      value: z.number().int().nonnegative(),
    }),
  ),
  recentProperties: z.array(propertyListItemSchema).max(4),
})

export type Session = z.infer<typeof sessionSchema>
export type PropertyListItem = z.infer<typeof propertyListItemSchema>
export type PropertyListResponse = z.infer<typeof propertyListResponseSchema>
export type Overview = z.infer<typeof overviewSchema>
