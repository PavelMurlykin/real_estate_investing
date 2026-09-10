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

export const customerListItemSchema = z.object({
  id: z.number().int().positive(),
  fullName: z.string(),
  phone: z.string(),
  email: z.string(),
  residenceCity: z.string().nullable(),
  createdAt: z.iso.datetime({ offset: true }),
  isActive: z.boolean(),
  legacyDetailUrl: z.string(),
})

export const customerListResponseSchema = z.object({
  page: z.number().int().positive(),
  pageSize: z.number().int().positive(),
  totalCount: z.number().int().nonnegative(),
  totalPages: z.number().int().nonnegative(),
  results: z.array(customerListItemSchema),
})

export const customerDetailSchema = z.object({
  id: z.number().int().positive(),
  firstName: z.string(),
  lastName: z.string(),
  fullName: z.string(),
  phone: z.string(),
  email: z.string(),
  age: z.number().int().nonnegative().nullable(),
  birthDate: z.iso.date().nullable(),
  birthYear: z.number().int().nullable(),
  residenceCity: z.string().nullable(),
  residenceCityId: z.number().int().positive().nullable(),
  initialPaymentAmount: z.string().nullable(),
  maximumMonthlyPayment: z.string().nullable(),
  preferentialPrograms: z.array(
    z.object({
      id: z.number().int().positive(),
      name: z.string(),
    }),
  ),
  hasOwnedProperty: z.boolean().nullable(),
  purchaseGoal: z.string(),
  purchaseGoalLabel: z.string(),
  desiredCity: z.string().nullable(),
  desiredCityId: z.number().int().positive().nullable(),
  desiredDistrict: z.string().nullable(),
  desiredDistrictId: z.number().int().positive().nullable(),
  desiredLayouts: z.array(
    z.object({
      id: z.number().int().positive(),
      name: z.string(),
    }),
  ),
  areaMinimum: z.string().nullable(),
  areaMaximum: z.string().nullable(),
  desiredFloor: z.string(),
  cardinalDirections: z.string(),
  comment: z.string(),
  calculated: z.object({
    maximumTermYears: z.number().int().nonnegative(),
    actualKeyRate: z.string(),
    annualRate: z.string(),
    maximumPropertyCost: z.string().nullable(),
    hasPreferentialProgram: z.boolean(),
    preferentialAnnualRate: z.string(),
    preferentialMaximumPropertyCost: z.string().nullable(),
    preferentialCreditLimit: z.string().nullable(),
  }),
  isActive: z.boolean(),
  createdAt: z.iso.datetime({ offset: true }),
  updatedAt: z.iso.datetime({ offset: true }),
  legacyDetailUrl: z.string(),
  legacyEditUrl: z.string(),
  legacyDeleteUrl: z.string(),
  legacyMortgageUrl: z.string(),
})

const namedOptionSchema = z.object({
  id: z.number().int().positive(),
  name: z.string(),
})

export const customerFormOptionsSchema = z.object({
  cities: z.array(namedOptionSchema),
  districts: z.array(namedOptionSchema),
  layouts: z.array(namedOptionSchema),
  preferentialPrograms: z.array(namedOptionSchema),
  purchaseGoals: z.array(
    z.object({
      value: z.string(),
      label: z.string(),
    }),
  ),
  cardinalDirections: z.array(
    z.object({
      value: z.string(),
      label: z.string(),
    }),
  ),
  truncated: z.object({
    cities: z.boolean(),
    districts: z.boolean(),
    layouts: z.boolean(),
    preferentialPrograms: z.boolean(),
  }),
})

export const customerMutationResponseSchema = z.object({
  id: z.number().int().positive(),
})

export const propertyDetailSchema = z.object({
  id: z.number().int().positive(),
  apartmentNumber: z.string(),
  developer: z.string(),
  realEstateComplex: z.string(),
  realEstateClass: z.string(),
  realEstateType: z.string(),
  district: z.string(),
  city: z.string(),
  region: z.string(),
  building: z.string(),
  buildingAddress: z.string().nullable(),
  commissioning: z.string().nullable(),
  keyHandover: z.string().nullable(),
  layout: z.string(),
  layoutDescription: z.string().nullable(),
  decoration: z.string(),
  decorationDescription: z.string().nullable(),
  windowViews: z.array(z.string()),
  area: z.string(),
  floor: z.number().int(),
  propertyCost: z.string(),
  mapUrl: z.string().nullable(),
  presentationUrl: z.string().nullable(),
  images: z.array(
    z.object({
      kind: z.enum(['layout', 'floorPlan', 'windowView']),
      label: z.string(),
      url: z.string().nullable(),
    }),
  ).max(3),
  createdAt: z.iso.datetime({ offset: true }),
  updatedAt: z.iso.datetime({ offset: true }),
  legacyDetailUrl: z.string(),
  legacyEditUrl: z.string(),
  legacyDeleteUrl: z.string(),
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

export const mortgageOptionsSchema = z.object({
  defaultInitialPaymentDate: z.iso.date(),
  keyRate: z.string(),
  banks: z.array(
    z.object({
      id: z.number().int().positive(),
      name: z.string(),
      logoUrl: z.string(),
    }),
  ),
  programs: z.array(
    z.object({
      id: z.number().int().positive(),
      bankId: z.number().int().positive(),
      programId: z.number().int().positive(),
      programName: z.string(),
      interestRate: z.string(),
      minimumInitialPaymentPercent: z.string(),
      maximumLoanTermYears: z.number().int().positive().nullable(),
      isPreferential: z.boolean(),
      creditLimit: z.string().nullable(),
      regionalCreditLimits: z.array(
        z.object({
          regionId: z.number().int().positive(),
          creditLimit: z.string(),
        }),
      ),
    }),
  ),
})

const mortgageAssumptionsSchema = z.object({
  basePropertyCost: z.string(),
  priceAdjustmentType: z.enum(['discount', 'markup']),
  priceAdjustmentPercent: z.string(),
  priceAdjustmentRubles: z.string(),
  finalPropertyCost: z.string(),
  initialPaymentPercent: z.string(),
  initialPaymentRubles: z.string(),
  initialPaymentDate: z.iso.date(),
  mortgageTermMonths: z.number().int().positive(),
  annualRate: z.string(),
  hasGracePeriod: z.boolean(),
  gracePeriodTermMonths: z.number().int().nonnegative(),
  gracePeriodRate: z.string().nullable(),
})

const mortgageSummarySchema = z.object({
  loanAmount: z.string(),
  mainMonthlyPayment: z.string(),
  graceMonthlyPayment: z.string().nullable(),
  overpayment: z.string(),
  totalPayments: z.string(),
  paymentsCount: z.number().int().positive(),
  mortgageEndDate: z.iso.date(),
  gracePeriodEndDate: z.iso.date().nullable(),
})

const mortgagePaymentSchema = z.object({
  paymentNumber: z.number().int().positive(),
  paymentDate: z.iso.date(),
  paymentAmount: z.string(),
  interestAmount: z.string(),
  principalAmount: z.string(),
  remainingDebt: z.string(),
})

export const mortgageCalculationResponseSchema = z.object({
  assumptions: mortgageAssumptionsSchema,
  summary: mortgageSummarySchema,
  schedule: z.array(mortgagePaymentSchema).max(600),
})

const savedMortgagePropertySchema = z.object({
  id: z.number().int().positive(),
  city: z.string(),
  developer: z.string(),
  realEstateComplex: z.string(),
  realEstateClass: z.string(),
  building: z.string(),
  apartmentNumber: z.string(),
  layout: z.string(),
  decoration: z.string(),
  area: z.string(),
  floor: z.number().int(),
  detailUrl: z.string(),
})

export const savedMortgageCalculationListItemSchema = z.object({
  id: z.number().int().positive(),
  createdAt: z.iso.datetime({ offset: true }),
  property: savedMortgagePropertySchema,
  finalPropertyCost: z.string(),
  initialPaymentRubles: z.string(),
  mainMonthlyPayment: z.string().nullable(),
  mortgageTermMonths: z.number().int().positive(),
  annualRate: z.string(),
})

export const savedMortgageCalculationListResponseSchema = z.object({
  page: z.number().int().positive(),
  pageSize: z.number().int().positive(),
  totalCount: z.number().int().nonnegative(),
  totalPages: z.number().int().nonnegative(),
  results: z.array(savedMortgageCalculationListItemSchema),
})

export const savedMortgageCalculationDetailSchema = z.object({
  id: z.number().int().positive(),
  createdAt: z.iso.datetime({ offset: true }),
  property: savedMortgagePropertySchema,
  legacyDetailUrl: z.string(),
  legacySampleUrl: z.string(),
  calculation: mortgageCalculationResponseSchema,
})

export type MortgageCalculationRequest = {
  propertyCost: string
  priceAdjustmentType: 'discount' | 'markup'
  priceAdjustmentUnit: 'percent' | 'rubles'
  priceAdjustmentValue: string
  initialPaymentUnit: 'percent' | 'rubles'
  initialPaymentValue: string
  initialPaymentDate: string
  mortgageTermMonths: number
  annualRate: string
  hasGracePeriod: boolean
  gracePeriodTermMonths?: number
  gracePeriodRate?: string
}

export type SavedMortgageCalculationCreateRequest = {
  propertyId: number
  parameters: MortgageCalculationRequest
}

export type Session = z.infer<typeof sessionSchema>
export type PropertyListItem = z.infer<typeof propertyListItemSchema>
export type PropertyListResponse = z.infer<typeof propertyListResponseSchema>
export type CustomerListItem = z.infer<typeof customerListItemSchema>
export type CustomerListResponse = z.infer<typeof customerListResponseSchema>
export type CustomerDetail = z.infer<typeof customerDetailSchema>
export type CustomerFormOptions = z.infer<typeof customerFormOptionsSchema>
export type PropertyDetail = z.infer<typeof propertyDetailSchema>
export type Overview = z.infer<typeof overviewSchema>
export type MortgageOptions = z.infer<typeof mortgageOptionsSchema>
export type MortgageCalculationResponse = z.infer<
  typeof mortgageCalculationResponseSchema
>
export type SavedMortgageCalculationListItem = z.infer<
  typeof savedMortgageCalculationListItemSchema
>
export type SavedMortgageCalculationListResponse = z.infer<
  typeof savedMortgageCalculationListResponseSchema
>
export type SavedMortgageCalculationDetail = z.infer<
  typeof savedMortgageCalculationDetailSchema
>

export type CustomerWriteRequest = {
  firstName: string
  lastName: string
  phone: string
  email: string
  age: number | null
  birthDate: string | null
  birthYear: number | null
  residenceCityId: number | null
  initialPaymentAmount: string | null
  maximumMonthlyPayment: string | null
  preferentialProgramIds: number[]
  hasOwnedProperty: boolean | null
  purchaseGoal: string
  desiredCityId: number | null
  desiredDistrictId: number | null
  desiredLayoutIds: number[]
  areaMinimum: string | null
  areaMaximum: string | null
  desiredFloor: string
  cardinalDirections: string[]
  comment: string
}
