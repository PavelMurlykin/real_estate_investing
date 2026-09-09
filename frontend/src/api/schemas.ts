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

export type Session = z.infer<typeof sessionSchema>
export type PropertyListItem = z.infer<typeof propertyListItemSchema>
export type PropertyListResponse = z.infer<typeof propertyListResponseSchema>
export type Overview = z.infer<typeof overviewSchema>
export type MortgageOptions = z.infer<typeof mortgageOptionsSchema>
export type MortgageCalculationResponse = z.infer<
  typeof mortgageCalculationResponseSchema
>
