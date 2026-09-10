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

export const companyGroupSchema = z.object({
  id: z.number().int().positive(),
  name: z.string(),
  developerCount: z.number().int().nonnegative(),
  legacyEditUrl: z.string(),
  legacyDeleteUrl: z.string(),
})

export const companyGroupListResponseSchema = z.object({
  page: z.number().int().positive(),
  pageSize: z.number().int().positive(),
  totalCount: z.number().int().nonnegative(),
  totalPages: z.number().int().nonnegative(),
  results: z.array(companyGroupSchema),
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

export const developerPublicSchema = z.object({
  id: z.number().int().positive(),
  name: z.string(),
  companyGroup: namedOptionSchema.nullable(),
  regions: z.array(namedOptionSchema),
  complexCount: z.number().int().nonnegative(),
  isActive: z.boolean(),
})

export const developerSchema = developerPublicSchema.extend({
  description: z.string().nullable(),
  legalAddress: z.string().nullable(),
  actualAddress: z.string().nullable(),
  taxpayerIdentificationNumber: z.string().nullable(),
  taxRegistrationReasonCode: z.string().nullable(),
  primaryStateRegistrationNumber: z.string().nullable(),
  createdAt: z.iso.datetime({ offset: true }),
  updatedAt: z.iso.datetime({ offset: true }),
  legacyEditUrl: z.string(),
  legacyDeleteUrl: z.string(),
})

export const developerListResponseSchema = z.object({
  page: z.number().int().positive(),
  pageSize: z.number().int().positive(),
  totalCount: z.number().int().nonnegative(),
  totalPages: z.number().int().nonnegative(),
  results: z.array(developerPublicSchema),
})

export const developerOptionsSchema = z.object({
  companyGroups: z.array(namedOptionSchema),
  regions: z.array(namedOptionSchema),
  truncated: z.object({
    companyGroups: z.boolean(),
    regions: z.boolean(),
  }),
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
  regionId: z.number().int().positive(),
  cityId: z.number().int().positive(),
  districtId: z.number().int().positive(),
  developerId: z.number().int().positive(),
  realEstateComplexId: z.number().int().positive(),
  buildingId: z.number().int().positive(),
  layoutId: z.number().int().positive(),
  decorationId: z.number().int().positive(),
  windowViewIds: z.array(z.number().int().positive()),
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

export const propertyFormOptionsSchema = z.object({
  regions: z.array(namedOptionSchema),
  cities: z.array(namedOptionSchema),
  districts: z.array(namedOptionSchema),
  developers: z.array(
    z.object({
      id: z.number().int().positive(),
      label: z.string(),
    }),
  ),
  realEstateComplexes: z.array(namedOptionSchema),
  buildings: z.array(
    z.object({
      id: z.number().int().positive(),
      number: z.string(),
    }),
  ),
  layouts: z.array(namedOptionSchema),
  decorations: z.array(namedOptionSchema),
  windowViews: z.array(namedOptionSchema),
  truncated: z.object({
    regions: z.boolean(),
    cities: z.boolean(),
    districts: z.boolean(),
    developers: z.boolean(),
    realEstateComplexes: z.boolean(),
    buildings: z.boolean(),
    layouts: z.boolean(),
    decorations: z.boolean(),
    windowViews: z.boolean(),
  }),
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

const trenchMortgageAssumptionsSchema = z.object({
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
  trenchCount: z.number().int().min(1).max(5),
})

const trenchMortgageSummarySchema = z.object({
  loanAmount: z.string(),
  maximumMonthlyPayment: z.string(),
  overpayment: z.string(),
  totalPayments: z.string(),
  paymentsCount: z.number().int().positive(),
  mortgageEndDate: z.iso.date(),
})

const trenchMortgageEntrySchema = z.object({
  number: z.number().int().min(1).max(5),
  date: z.iso.date(),
  percent: z.string(),
  amount: z.string(),
  annualRate: z.string(),
  monthlyPayment: z.string(),
  paymentsCount: z.number().int().nonnegative(),
  remainingDebt: z.string(),
  overpayment: z.string(),
})

export const trenchMortgageCalculationResponseSchema = z.object({
  assumptions: trenchMortgageAssumptionsSchema,
  summary: trenchMortgageSummarySchema,
  trenches: z.array(trenchMortgageEntrySchema).min(1).max(5),
  schedule: z.array(mortgagePaymentSchema).max(600),
})

export const savedTrenchMortgageCalculationCreateResponseSchema = z.object({
  id: z.number().int().positive(),
  legacyDetailUrl: z.string(),
  calculation: trenchMortgageCalculationResponseSchema,
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
  isLinked: z.boolean(),
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

export const savedTrenchMortgageCalculationListItemSchema = z.object({
  id: z.number().int().positive(),
  createdAt: z.iso.datetime({ offset: true }),
  property: savedMortgagePropertySchema,
  finalPropertyCost: z.string(),
  initialPaymentRubles: z.string(),
  maximumMonthlyPayment: z.string().nullable(),
  mortgageTermMonths: z.number().int().positive(),
  annualRate: z.string(),
  trenchCount: z.number().int().min(1).max(5),
  isLinked: z.boolean(),
})

export const savedTrenchMortgageCalculationListResponseSchema = z.object({
  page: z.number().int().positive(),
  pageSize: z.number().int().positive(),
  totalCount: z.number().int().nonnegative(),
  totalPages: z.number().int().nonnegative(),
  results: z.array(savedTrenchMortgageCalculationListItemSchema),
})

export const savedTrenchMortgageCalculationDetailSchema = z.object({
  id: z.number().int().positive(),
  createdAt: z.iso.datetime({ offset: true }),
  property: savedMortgagePropertySchema,
  legacyDetailUrl: z.string(),
  calculation: trenchMortgageCalculationResponseSchema,
})

export const customerCalculationListItemSchema = z.object({
  linkId: z.number().int().positive(),
  calculationId: z.number().int().positive(),
  programType: z.enum(['market', 'trench']),
  createdAt: z.iso.datetime({ offset: true }),
  property: z.object({
    id: z.number().int().positive(),
    city: z.string(),
    realEstateComplex: z.string(),
    building: z.string(),
    apartmentNumber: z.string(),
  }),
  finalPropertyCost: z.string(),
  initialPaymentRubles: z.string(),
  monthlyPayment: z.string().nullable(),
  mortgageTermMonths: z.number().int().positive(),
  annualRate: z.string(),
  trenchCount: z.number().int().positive(),
})

export const customerCalculationListResponseSchema = z.object({
  page: z.number().int().positive(),
  pageSize: z.number().int().positive(),
  totalCount: z.number().int().nonnegative(),
  totalPages: z.number().int().nonnegative(),
  results: z.array(customerCalculationListItemSchema),
})

export const customerCalculationLinkResponseSchema = z.object({
  createdCount: z.number().int().nonnegative(),
  linkedCalculationIds: z.array(z.number().int().positive()),
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
  customerId?: number
}

export type TrenchMortgageEntryRequest = {
  date: string
  amountUnit: 'percent' | 'rubles'
  amountValue: string | null
  annualRate: string
}

export type TrenchMortgageCalculationRequest = {
  propertyCost: string
  priceAdjustmentType: 'discount' | 'markup'
  priceAdjustmentUnit: 'percent' | 'rubles'
  priceAdjustmentValue: string
  initialPaymentUnit: 'percent' | 'rubles'
  initialPaymentValue: string
  initialPaymentDate: string
  mortgageTermMonths: number
  annualRate: string
  trenches: TrenchMortgageEntryRequest[]
}

export type SavedTrenchMortgageCalculationCreateRequest = {
  propertyId: number
  parameters: TrenchMortgageCalculationRequest
  customerId?: number
}

export type CustomerCalculationProgramType = 'market' | 'trench'

export type CustomerCalculationLinkCreateRequest = {
  programType: CustomerCalculationProgramType
  calculationIds: number[]
}

export type CustomerCalculationSelection = {
  programType: CustomerCalculationProgramType
  linkId: number
}

export type Session = z.infer<typeof sessionSchema>
export type PropertyListItem = z.infer<typeof propertyListItemSchema>
export type PropertyListResponse = z.infer<typeof propertyListResponseSchema>
export type CompanyGroup = z.infer<typeof companyGroupSchema>
export type CompanyGroupListResponse = z.infer<
  typeof companyGroupListResponseSchema
>
export type DeveloperPublic = z.infer<typeof developerPublicSchema>
export type Developer = z.infer<typeof developerSchema>
export type DeveloperListResponse = z.infer<
  typeof developerListResponseSchema
>
export type DeveloperOptions = z.infer<typeof developerOptionsSchema>
export type CustomerListItem = z.infer<typeof customerListItemSchema>
export type CustomerListResponse = z.infer<typeof customerListResponseSchema>
export type CustomerDetail = z.infer<typeof customerDetailSchema>
export type CustomerFormOptions = z.infer<typeof customerFormOptionsSchema>
export type PropertyDetail = z.infer<typeof propertyDetailSchema>
export type PropertyFormOptions = z.infer<typeof propertyFormOptionsSchema>
export type Overview = z.infer<typeof overviewSchema>
export type MortgageOptions = z.infer<typeof mortgageOptionsSchema>
export type MortgageCalculationResponse = z.infer<
  typeof mortgageCalculationResponseSchema
>
export type TrenchMortgageCalculationResponse = z.infer<
  typeof trenchMortgageCalculationResponseSchema
>
export type SavedTrenchMortgageCalculationCreateResponse = z.infer<
  typeof savedTrenchMortgageCalculationCreateResponseSchema
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
export type SavedTrenchMortgageCalculationListItem = z.infer<
  typeof savedTrenchMortgageCalculationListItemSchema
>
export type SavedTrenchMortgageCalculationListResponse = z.infer<
  typeof savedTrenchMortgageCalculationListResponseSchema
>
export type SavedTrenchMortgageCalculationDetail = z.infer<
  typeof savedTrenchMortgageCalculationDetailSchema
>
export type CustomerCalculationListItem = z.infer<
  typeof customerCalculationListItemSchema
>
export type CustomerCalculationListResponse = z.infer<
  typeof customerCalculationListResponseSchema
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

export type DeveloperWriteRequest = {
  name: string
  companyGroupId: number | null
  regionIds: number[]
  legalAddress: string | null
  actualAddress: string | null
  taxpayerIdentificationNumber: string | null
  taxRegistrationReasonCode: string | null
  primaryStateRegistrationNumber: string | null
  description: string | null
  isActive: boolean
}
