import type { DeveloperMortgageProgram, MortgageOptions } from '@/api/schemas'

export type BankMortgageProgram = MortgageOptions['programs'][number]

export function matchDeveloperProgram(
  programs: DeveloperMortgageProgram[],
  bankProgram: BankMortgageProgram,
  complexIdentifier: number | null,
) {
  const matching = programs.filter((program) => (
    program.bankId === bankProgram.bankId
    && program.mortgageProgramId === bankProgram.programId
  ))
  return matching.find((program) => (
    complexIdentifier !== null && program.realEstateComplexId === complexIdentifier
  )) ?? matching.find((program) => program.realEstateComplexId === null)
}

export function getProgramConditions(
  program: BankMortgageProgram,
  keyRate: string,
  developerProgram?: DeveloperMortgageProgram,
) {
  const baseRate = Number(program.interestRate) > 0
    ? program.interestRate
    : String(program.isPreferential ? 6 : Number(keyRate) + 2)
  const priceIncrease = developerProgram?.priceIncreasePercent
  const graceMonths = developerProgram?.gracePeriodMonths
  const graceRate = developerProgram?.gracePeriodInterestRate
  return {
    annualRate: developerProgram?.interestRate ?? baseRate,
    initialPaymentPercent: developerProgram?.minimumInitialPaymentPercent
      ?? (Number(program.minimumInitialPaymentPercent) > 0
        ? program.minimumInitialPaymentPercent : '20'),
    mortgageTermMonths: String((developerProgram?.maximumLoanTermYears
      ?? program.maximumLoanTermYears ?? 30) * 12),
    ...(priceIncrease !== undefined && priceIncrease !== null ? {
      priceAdjustmentType: Number(priceIncrease) > 0 ? 'markup' as const : 'discount' as const,
      priceAdjustmentPercent: String(Math.abs(Number(priceIncrease))),
    } : {}),
    ...(graceMonths && graceRate !== undefined && graceRate !== null ? {
      hasGracePeriod: true,
      gracePeriodTermMonths: String(graceMonths),
      gracePeriodTermYears: String(graceMonths / 12),
      gracePeriodRate: graceRate,
    } : {}),
  }
}

export function getProgramCreditLimit(
  program: BankMortgageProgram,
  regionIdentifier: number | null,
  developerProgram?: DeveloperMortgageProgram,
) {
  const regional = program.regionalCreditLimits.find(
    (limit) => limit.regionId === regionIdentifier,
  )
  const programLimit = program.isPreferential
    ? Number(regional?.creditLimit ?? program.creditLimit ?? 0) : 0
  const developerLimit = Number(developerProgram?.maximumLoanAmount ?? 0)
  const limits = [programLimit, developerLimit].filter((limit) => limit > 0)
  return limits.length ? Math.min(...limits) : null
}
