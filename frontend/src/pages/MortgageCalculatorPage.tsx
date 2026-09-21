import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent, RefObject } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  calculateMortgage,
  calculateTrenchMortgage,
  mortgageOptionsQueryOptions,
  propertyDetailQueryOptions,
  propertyListQueryOptions,
  saveMortgageCalculation,
  saveTrenchMortgageCalculation,
  savedMortgageCalculationDetailQueryOptions,
  savedTrenchMortgageCalculationDetailQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type {
  MortgageCalculationRequest,
  MortgageCalculationResponse,
  PropertyDetail,
  PropertyListItem,
  TrenchMortgageCalculationRequest,
  TrenchMortgageCalculationResponse,
  TrenchMortgageEntryRequest,
} from '@/api/schemas'
import { MortgageResult } from '@/features/mortgage/MortgageResult'
import { TrenchMortgageResult } from '@/features/mortgage/TrenchMortgageResult'
import { formatPercent } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'

type CalculationType = 'market' | 'trench'
type ValueSource = 'percent' | 'rubles'

type PropertyDataState = {
  city: string
  district: string
  developer: string
  realEstateComplex: string
  building: string
  apartmentNumber: string
  area: string
  layout: string
  floor: string
  decoration: string
}

type TrenchRowState = {
  date: string
  amountSource: ValueSource
  amountPercent: string
  amountRubles: string
  annualRate: string
}

type MortgageFormState = {
  propertyCost: string
  priceAdjustmentType: 'discount' | 'markup'
  priceAdjustmentSource: ValueSource
  priceAdjustmentPercent: string
  priceAdjustmentRubles: string
  initialPaymentSource: ValueSource
  initialPaymentPercent: string
  initialPaymentRubles: string
  initialPaymentDate: string
  mortgageTermYears: string
  mortgageTermMonths: string
  annualRate: string
  bankId: string
  bankProgramId: string
  hasGracePeriod: boolean
  gracePeriodTermYears: string
  gracePeriodTermMonths: string
  gracePeriodRate: string
  trenchCount: number
  trenches: TrenchRowState[]
}

type FieldErrors = Record<string, string>

const EMPTY_PROPERTY_DATA: PropertyDataState = {
  city: '',
  district: '',
  developer: '',
  realEstateComplex: '',
  building: '',
  apartmentNumber: '',
  area: '',
  layout: '',
  floor: '',
  decoration: '',
}

function getLocalDateInputValue() {
  const currentDate = new Date()
  const timezoneOffset = currentDate.getTimezoneOffset() * 60_000
  return new Date(currentDate.getTime() - timezoneOffset)
    .toISOString()
    .slice(0, 10)
}

function formatCalculatedValue(value: number, fractionDigits = 2) {
  if (!Number.isFinite(value)) return ''
  return value.toFixed(fractionDigits).replace(/\.0+$|(?<=\.[0-9]*?)0+$/g, '')
}

function numberValue(value: string) {
  if (value.trim() === '') return null
  const parsedValue = Number(value)
  return Number.isFinite(parsedValue) ? parsedValue : null
}

function calculateAdjustmentRubles(propertyCost: string, percent: string) {
  const cost = numberValue(propertyCost)
  const percentage = numberValue(percent)
  if (cost === null || percentage === null) return ''
  return formatCalculatedValue(cost * percentage / 100)
}

function calculatePercent(baseValue: number, rubles: string) {
  const rubleValue = numberValue(rubles)
  if (rubleValue === null || baseValue <= 0) return ''
  return formatCalculatedValue(rubleValue / baseValue * 100)
}

function getFinalPropertyCost(formState: MortgageFormState) {
  const propertyCost = numberValue(formState.propertyCost) ?? 0
  const adjustmentRubles = numberValue(formState.priceAdjustmentRubles) ?? 0
  return formState.priceAdjustmentType === 'discount'
    ? Math.max(0, propertyCost - adjustmentRubles)
    : propertyCost + adjustmentRubles
}

function getLoanAmount(formState: MortgageFormState) {
  return Math.max(
    0,
    getFinalPropertyCost(formState)
      - (numberValue(formState.initialPaymentRubles) ?? 0),
  )
}

function synchronizeMoneyFields(formState: MortgageFormState) {
  let priceAdjustmentPercent = formState.priceAdjustmentPercent
  let priceAdjustmentRubles = formState.priceAdjustmentRubles
  if (formState.priceAdjustmentSource === 'percent') {
    priceAdjustmentRubles = calculateAdjustmentRubles(
      formState.propertyCost,
      priceAdjustmentPercent,
    )
  } else {
    priceAdjustmentPercent = calculatePercent(
      numberValue(formState.propertyCost) ?? 0,
      priceAdjustmentRubles,
    )
  }

  const stateWithAdjustment = {
    ...formState,
    priceAdjustmentPercent,
    priceAdjustmentRubles,
  }
  const finalPropertyCost = getFinalPropertyCost(stateWithAdjustment)
  let initialPaymentPercent = formState.initialPaymentPercent
  let initialPaymentRubles = formState.initialPaymentRubles
  if (formState.initialPaymentSource === 'percent') {
    const percent = numberValue(initialPaymentPercent)
    initialPaymentRubles = percent === null
      ? ''
      : formatCalculatedValue(finalPropertyCost * percent / 100)
  } else {
    initialPaymentPercent = calculatePercent(
      finalPropertyCost,
      initialPaymentRubles,
    )
  }

  const stateWithInitialPayment = {
    ...stateWithAdjustment,
    initialPaymentPercent,
    initialPaymentRubles,
  }
  const loanAmount = getLoanAmount(stateWithInitialPayment)
  return {
    ...stateWithInitialPayment,
    trenches: stateWithInitialPayment.trenches.map((trench) => (
      trench.amountSource === 'percent'
        ? {
            ...trench,
            amountRubles: numberValue(trench.amountPercent) === null
              ? ''
              : formatCalculatedValue(
                  loanAmount * Number(trench.amountPercent) / 100,
                ),
          }
        : {
            ...trench,
            amountPercent: calculatePercent(loanAmount, trench.amountRubles),
          }
    )),
  }
}

function buildInitialTrenches(annualRate: string): TrenchRowState[] {
  return Array.from({ length: 5 }, (_, index) => ({
    date: '',
    amountSource: 'percent',
    amountPercent: index === 0 ? '50' : '',
    amountRubles: index === 0 ? '1600000' : '',
    annualRate,
  }))
}

function initialFormState(propertyCost: string): MortgageFormState {
  return synchronizeMoneyFields({
    propertyCost,
    priceAdjustmentType: 'discount',
    priceAdjustmentSource: 'percent',
    priceAdjustmentPercent: '0',
    priceAdjustmentRubles: '0',
    initialPaymentSource: 'percent',
    initialPaymentPercent: '20',
    initialPaymentRubles: '1000000',
    initialPaymentDate: '',
    mortgageTermYears: '30',
    mortgageTermMonths: '360',
    annualRate: '15',
    bankId: '',
    bankProgramId: '',
    hasGracePeriod: false,
    gracePeriodTermYears: '1',
    gracePeriodTermMonths: '12',
    gracePeriodRate: '6',
    trenchCount: 2,
    trenches: buildInitialTrenches('15'),
  })
}

function collectFieldErrors(
  value: unknown,
  prefix = '',
  result: FieldErrors = {},
): FieldErrors {
  if (typeof value === 'string' && prefix) {
    result[prefix] ??= value
    return result
  }
  if (Array.isArray(value)) {
    if (typeof value[0] === 'string' && prefix) {
      result[prefix] ??= value[0]
      return result
    }
    value.forEach((item, index) => {
      collectFieldErrors(item, prefix ? `${prefix}.${index}` : `${index}`, result)
    })
    return result
  }
  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([key, nestedValue]) => {
      collectFieldErrors(
        nestedValue,
        prefix ? `${prefix}.${key}` : key,
        result,
      )
    })
  }
  return result
}

function extractFieldErrors(error: unknown): FieldErrors {
  if (!(error instanceof ApiError) || !error.details) return {}
  return collectFieldErrors(error.details)
}

function FieldError({ fieldName, errors }: { fieldName: string; errors: FieldErrors }) {
  const message = errors[fieldName]
  if (!message) return null
  return <span className="field-error" id={`${fieldName}-error`}>{message}</span>
}

function propertyDataFromListItem(property: PropertyListItem): PropertyDataState {
  return {
    city: property.city,
    district: '',
    developer: property.developer,
    realEstateComplex: property.realEstateComplex,
    building: property.building,
    apartmentNumber: property.apartmentNumber,
    area: property.area,
    layout: property.layout,
    floor: String(property.floor),
    decoration: property.decoration,
  }
}

function propertyDataFromDetail(property: PropertyDetail): PropertyDataState {
  return {
    city: property.city,
    district: property.district,
    developer: property.developer,
    realEstateComplex: property.realEstateComplex,
    building: property.building,
    apartmentNumber: property.apartmentNumber,
    area: property.area,
    layout: property.layout,
    floor: String(property.floor),
    decoration: property.decoration,
  }
}

function buildMarketPayload(
  formState: MortgageFormState,
  initialPaymentDate: string,
): MortgageCalculationRequest {
  const payload: MortgageCalculationRequest = {
    propertyCost: formState.propertyCost,
    priceAdjustmentType: formState.priceAdjustmentType,
    priceAdjustmentUnit: formState.priceAdjustmentSource,
    priceAdjustmentValue: formState.priceAdjustmentSource === 'percent'
      ? formState.priceAdjustmentPercent
      : formState.priceAdjustmentRubles,
    initialPaymentUnit: formState.initialPaymentSource,
    initialPaymentValue: formState.initialPaymentSource === 'percent'
      ? formState.initialPaymentPercent
      : formState.initialPaymentRubles,
    initialPaymentDate,
    mortgageTermMonths: Number(formState.mortgageTermMonths),
    annualRate: formState.annualRate,
    hasGracePeriod: formState.hasGracePeriod,
  }
  if (formState.hasGracePeriod) {
    payload.gracePeriodTermMonths = Number(formState.gracePeriodTermMonths)
    payload.gracePeriodRate = formState.gracePeriodRate
  }
  return payload
}

function buildTrenchPayload(
  formState: MortgageFormState,
  initialPaymentDate: string,
): TrenchMortgageCalculationRequest {
  const trenches: TrenchMortgageEntryRequest[] = formState.trenches
    .slice(0, formState.trenchCount)
    .map((trench, index) => ({
      date: trench.date || (index === 0 ? initialPaymentDate : ''),
      amountUnit: trench.amountSource,
      amountValue: index === formState.trenchCount - 1
        ? null
        : trench.amountSource === 'percent'
          ? trench.amountPercent
          : trench.amountRubles,
      annualRate: trench.annualRate,
    }))
  return {
    propertyCost: formState.propertyCost,
    priceAdjustmentType: formState.priceAdjustmentType,
    priceAdjustmentUnit: formState.priceAdjustmentSource,
    priceAdjustmentValue: formState.priceAdjustmentSource === 'percent'
      ? formState.priceAdjustmentPercent
      : formState.priceAdjustmentRubles,
    initialPaymentUnit: formState.initialPaymentSource,
    initialPaymentValue: formState.initialPaymentSource === 'percent'
      ? formState.initialPaymentPercent
      : formState.initialPaymentRubles,
    initialPaymentDate,
    mortgageTermMonths: Number(formState.mortgageTermMonths),
    annualRate: formState.annualRate,
    trenches,
  }
}

function ResultRegion({
  calculationType,
  marketResult,
  trenchResult,
  marketResultHeadingRef,
  trenchResultHeadingRef,
  action,
}: {
  calculationType: CalculationType
  marketResult?: MortgageCalculationResponse
  trenchResult?: TrenchMortgageCalculationResponse
  marketResultHeadingRef: RefObject<HTMLHeadingElement | null>
  trenchResultHeadingRef: RefObject<HTMLHeadingElement | null>
  action: React.ReactNode
}) {
  if (calculationType === 'market' && marketResult) {
    return (
      <MortgageResult
        headingRef={marketResultHeadingRef}
        result={marketResult}
        summaryAction={action}
      />
    )
  }
  if (calculationType === 'trench' && trenchResult) {
    return (
      <TrenchMortgageResult
        headingRef={trenchResultHeadingRef}
        result={trenchResult}
        summaryAction={action}
      />
    )
  }
  return null
}

export function MortgageCalculatorPage({
  initialCalculationType = 'market',
}: {
  initialCalculationType?: CalculationType
}) {
  useDocumentTitle('Ипотечный калькулятор')
  const [searchParameters] = useSearchParams()
  const location = useLocation()
  const queryClient = useQueryClient()
  const optionsQuery = useQuery(mortgageOptionsQueryOptions)
  const sessionQuery = useQuery(sessionQueryOptions)
  const propertyListParameters = useMemo(
    () => new URLSearchParams({ pageSize: '100', ordering: 'realEstateComplex' }),
    [],
  )
  const propertyListQuery = useQuery({
    ...propertyListQueryOptions(propertyListParameters),
    staleTime: 60_000,
  })
  const propertyItems = useMemo(
    () => propertyListQuery.data?.results ?? [],
    [propertyListQuery.data?.results],
  )
  const marketResultHeadingRef = useRef<HTMLHeadingElement>(null)
  const trenchResultHeadingRef = useRef<HTMLHeadingElement>(null)
  const appliedSampleIdentifierRef = useRef<string | null>(null)
  const appliedPropertyIdentifierRef = useRef<number | null>(null)
  const rawPropertyIdentifier = Number(searchParameters.get('propertyId'))
  const directPropertyIdentifier = Number.isInteger(rawPropertyIdentifier)
    && rawPropertyIdentifier > 0
    ? rawPropertyIdentifier
    : null
  const rawCustomerIdentifier = Number(searchParameters.get('customerId'))
  const customerIdentifier = Number.isInteger(rawCustomerIdentifier)
    && rawCustomerIdentifier > 0
    ? rawCustomerIdentifier
    : null
  const rawSampleIdentifier = Number(searchParameters.get('sample'))
  const sampleIdentifier = Number.isInteger(rawSampleIdentifier)
    && rawSampleIdentifier > 0
    ? rawSampleIdentifier
    : null
  const [calculationType, setCalculationType] = useState<CalculationType>(
    initialCalculationType,
  )
  const marketSampleQuery = useQuery({
    ...savedMortgageCalculationDetailQueryOptions(sampleIdentifier ?? 0),
    staleTime: 60_000,
    enabled: calculationType === 'market'
      && sessionQuery.data?.isAuthenticated === true
      && sampleIdentifier !== null,
  })
  const trenchSampleQuery = useQuery({
    ...savedTrenchMortgageCalculationDetailQueryOptions(sampleIdentifier ?? 0),
    staleTime: 60_000,
    enabled: calculationType === 'trench'
      && sessionQuery.data?.isAuthenticated === true
      && sampleIdentifier !== null,
  })
  const [selectedPropertyIdentifier, setSelectedPropertyIdentifier] = useState<
    number | null
  >(directPropertyIdentifier)
  const selectedPropertyQuery = useQuery({
    ...propertyDetailQueryOptions(selectedPropertyIdentifier ?? 0),
    enabled: selectedPropertyIdentifier !== null
      && !propertyItems.some(
        (property) => property.id === selectedPropertyIdentifier,
      ),
  })
  const [propertyData, setPropertyData] = useState<PropertyDataState>(
    EMPTY_PROPERTY_DATA,
  )
  const [formState, setFormState] = useState<MortgageFormState>(() => (
    initialFormState(searchParameters.get('propertyCost') ?? '5000000')
  ))
  const marketCalculationMutation = useMutation({ mutationFn: calculateMortgage })
  const trenchCalculationMutation = useMutation({
    mutationFn: calculateTrenchMortgage,
  })
  const marketSaveMutation = useMutation({
    mutationFn: saveMortgageCalculation,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['saved-mortgage-calculations'],
      })
      if (customerIdentifier) {
        await queryClient.invalidateQueries({
          queryKey: ['customer-calculations', customerIdentifier],
        })
      }
    },
  })
  const trenchSaveMutation = useMutation({
    mutationFn: saveTrenchMortgageCalculation,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['saved-trench-mortgage-calculations'],
      })
      if (customerIdentifier) {
        await queryClient.invalidateQueries({
          queryKey: ['customer-calculations', customerIdentifier],
        })
      }
    },
  })
  const activeCalculationMutation = calculationType === 'market'
    ? marketCalculationMutation
    : trenchCalculationMutation
  const activeSaveMutation = calculationType === 'market'
    ? marketSaveMutation
    : trenchSaveMutation
  const activeSampleQuery = calculationType === 'market'
    ? marketSampleQuery
    : trenchSampleQuery
  const fieldErrors = extractFieldErrors(activeCalculationMutation.error)
  const initialPaymentDate = formState.initialPaymentDate
    || optionsQuery.data?.defaultInitialPaymentDate
    || getLocalDateInputValue()
  const availablePrograms = useMemo(
    () => optionsQuery.data?.programs.filter(
      (program) => String(program.bankId) === formState.bankId,
    ) ?? [],
    [formState.bankId, optionsQuery.data],
  )
  const finalPropertyCost = getFinalPropertyCost(formState)
  const loanAmount = getLoanAmount(formState)
  const calculationQueryString = searchParameters.toString()
  const loginReturnPath = `${location.pathname}${
    calculationQueryString ? `?${calculationQueryString}` : ''
  }`

  useEffect(() => {
    if (!selectedPropertyIdentifier) return
    const property = propertyItems.find(
      (item) => item.id === selectedPropertyIdentifier,
    )
    if (!property || appliedPropertyIdentifierRef.current === property.id) return
    setPropertyData(propertyDataFromListItem(property))
    setFormState((current) => synchronizeMoneyFields({
      ...current,
      propertyCost: searchParameters.has('propertyCost')
        ? current.propertyCost
        : property.propertyCost,
    }))
    appliedPropertyIdentifierRef.current = property.id
  }, [propertyItems, searchParameters, selectedPropertyIdentifier])

  useEffect(() => {
    const property = selectedPropertyQuery.data
    if (!property || appliedPropertyIdentifierRef.current === property.id) return
    setPropertyData(propertyDataFromDetail(property))
    setFormState((current) => synchronizeMoneyFields({
      ...current,
      propertyCost: searchParameters.has('propertyCost')
        ? current.propertyCost
        : property.propertyCost,
    }))
    appliedPropertyIdentifierRef.current = property.id
  }, [searchParameters, selectedPropertyQuery.data])

  useEffect(() => {
    if (calculationType !== 'market' || !marketSampleQuery.data) return
    const sampleKey = `market-${marketSampleQuery.data.id}`
    if (appliedSampleIdentifierRef.current === sampleKey) return
    const assumptions = marketSampleQuery.data.calculation.assumptions
    appliedPropertyIdentifierRef.current = marketSampleQuery.data.property.id
    setSelectedPropertyIdentifier(marketSampleQuery.data.property.id)
    setPropertyData({
      city: marketSampleQuery.data.property.city,
      district: '',
      developer: marketSampleQuery.data.property.developer,
      realEstateComplex: marketSampleQuery.data.property.realEstateComplex,
      building: marketSampleQuery.data.property.building,
      apartmentNumber: marketSampleQuery.data.property.apartmentNumber,
      area: marketSampleQuery.data.property.area,
      layout: marketSampleQuery.data.property.layout,
      floor: String(marketSampleQuery.data.property.floor),
      decoration: marketSampleQuery.data.property.decoration,
    })
    setFormState((current) => synchronizeMoneyFields({
      ...current,
      propertyCost: assumptions.basePropertyCost,
      priceAdjustmentType: assumptions.priceAdjustmentType,
      priceAdjustmentSource: 'percent',
      priceAdjustmentPercent: assumptions.priceAdjustmentPercent,
      priceAdjustmentRubles: assumptions.priceAdjustmentRubles,
      initialPaymentSource: 'percent',
      initialPaymentPercent: assumptions.initialPaymentPercent,
      initialPaymentRubles: assumptions.initialPaymentRubles,
      initialPaymentDate: assumptions.initialPaymentDate,
      mortgageTermYears: formatCalculatedValue(
        assumptions.mortgageTermMonths / 12,
      ),
      mortgageTermMonths: String(assumptions.mortgageTermMonths),
      annualRate: assumptions.annualRate,
      bankId: '',
      bankProgramId: '',
      hasGracePeriod: assumptions.hasGracePeriod,
      gracePeriodTermYears: formatCalculatedValue(
        assumptions.gracePeriodTermMonths / 12,
      ),
      gracePeriodTermMonths: String(
        assumptions.gracePeriodTermMonths || 12,
      ),
      gracePeriodRate: assumptions.gracePeriodRate ?? '6',
    }))
    appliedSampleIdentifierRef.current = sampleKey
  }, [calculationType, marketSampleQuery.data])

  useEffect(() => {
    if (calculationType !== 'trench' || !trenchSampleQuery.data) return
    const sampleKey = `trench-${trenchSampleQuery.data.id}`
    if (appliedSampleIdentifierRef.current === sampleKey) return
    const assumptions = trenchSampleQuery.data.calculation.assumptions
    const savedTrenches = trenchSampleQuery.data.calculation.trenches
    appliedPropertyIdentifierRef.current = trenchSampleQuery.data.property.id
    setSelectedPropertyIdentifier(trenchSampleQuery.data.property.id)
    setPropertyData({
      city: trenchSampleQuery.data.property.city,
      district: '',
      developer: trenchSampleQuery.data.property.developer,
      realEstateComplex: trenchSampleQuery.data.property.realEstateComplex,
      building: trenchSampleQuery.data.property.building,
      apartmentNumber: trenchSampleQuery.data.property.apartmentNumber,
      area: trenchSampleQuery.data.property.area,
      layout: trenchSampleQuery.data.property.layout,
      floor: String(trenchSampleQuery.data.property.floor),
      decoration: trenchSampleQuery.data.property.decoration,
    })
    setFormState((current) => synchronizeMoneyFields({
      ...current,
      propertyCost: assumptions.basePropertyCost,
      priceAdjustmentType: assumptions.priceAdjustmentType,
      priceAdjustmentSource: 'percent',
      priceAdjustmentPercent: assumptions.priceAdjustmentPercent,
      priceAdjustmentRubles: assumptions.priceAdjustmentRubles,
      initialPaymentSource: 'percent',
      initialPaymentPercent: assumptions.initialPaymentPercent,
      initialPaymentRubles: assumptions.initialPaymentRubles,
      initialPaymentDate: assumptions.initialPaymentDate,
      mortgageTermYears: formatCalculatedValue(
        assumptions.mortgageTermMonths / 12,
      ),
      mortgageTermMonths: String(assumptions.mortgageTermMonths),
      annualRate: assumptions.annualRate,
      bankId: '',
      bankProgramId: '',
      trenchCount: savedTrenches.length,
      trenches: buildInitialTrenches(assumptions.annualRate).map(
        (trench, index) => {
          const savedTrench = savedTrenches[index]
          if (!savedTrench) return trench
          return {
            date: savedTrench.date,
            amountSource: 'percent',
            amountPercent: index === savedTrenches.length - 1
              ? ''
              : savedTrench.percent,
            amountRubles: index === savedTrenches.length - 1
              ? ''
              : savedTrench.amount,
            annualRate: savedTrench.annualRate,
          }
        },
      ),
    }))
    appliedSampleIdentifierRef.current = sampleKey
  }, [calculationType, trenchSampleQuery.data])

  useEffect(() => {
    if (marketCalculationMutation.isSuccess) {
      marketResultHeadingRef.current?.focus({ preventScroll: true })
      marketResultHeadingRef.current?.scrollIntoView?.({ block: 'start' })
    }
  }, [marketCalculationMutation.data, marketCalculationMutation.isSuccess])

  useEffect(() => {
    if (trenchCalculationMutation.isSuccess) {
      trenchResultHeadingRef.current?.focus({ preventScroll: true })
      trenchResultHeadingRef.current?.scrollIntoView?.({ block: 'start' })
    }
  }, [trenchCalculationMutation.data, trenchCalculationMutation.isSuccess])

  const resetActiveErrors = () => {
    if (activeCalculationMutation.isError) activeCalculationMutation.reset()
  }

  const updateField = <FieldName extends keyof MortgageFormState>(
    fieldName: FieldName,
    value: MortgageFormState[FieldName],
  ) => {
    resetActiveErrors()
    setFormState((current) => ({ ...current, [fieldName]: value }))
  }

  const updatePropertyData = (
    fieldName: keyof PropertyDataState,
    value: string,
  ) => {
    setSelectedPropertyIdentifier(null)
    appliedPropertyIdentifierRef.current = null
    setPropertyData((current) => ({ ...current, [fieldName]: value }))
  }

  const selectProperty = (propertyIdentifier: string) => {
    const identifier = Number(propertyIdentifier)
    if (!Number.isInteger(identifier) || identifier <= 0) {
      setSelectedPropertyIdentifier(null)
      setPropertyData(EMPTY_PROPERTY_DATA)
      return
    }
    const property = propertyItems.find((item) => item.id === identifier)
    setSelectedPropertyIdentifier(identifier)
    appliedPropertyIdentifierRef.current = property ? identifier : null
    if (!property) return
    setPropertyData(propertyDataFromListItem(property))
    setFormState((current) => synchronizeMoneyFields({
      ...current,
      propertyCost: property.propertyCost,
    }))
  }

  const updatePropertyCost = (value: string) => {
    resetActiveErrors()
    setFormState((current) => synchronizeMoneyFields({
      ...current,
      propertyCost: value,
    }))
  }

  const updateAdjustment = (source: ValueSource, value: string) => {
    resetActiveErrors()
    setFormState((current) => synchronizeMoneyFields({
      ...current,
      priceAdjustmentSource: source,
      ...(source === 'percent'
        ? { priceAdjustmentPercent: value }
        : { priceAdjustmentRubles: value }),
    }))
  }

  const updateInitialPayment = (source: ValueSource, value: string) => {
    resetActiveErrors()
    setFormState((current) => synchronizeMoneyFields({
      ...current,
      initialPaymentSource: source,
      ...(source === 'percent'
        ? { initialPaymentPercent: value }
        : { initialPaymentRubles: value }),
    }))
  }

  const updateMortgageTermYears = (value: string) => {
    const years = numberValue(value)
    setFormState((current) => ({
      ...current,
      mortgageTermYears: value,
      mortgageTermMonths: years === null
        ? ''
        : String(Math.round(years * 12)),
    }))
  }

  const updateMortgageTermMonths = (value: string) => {
    const months = numberValue(value)
    setFormState((current) => ({
      ...current,
      mortgageTermMonths: value,
      mortgageTermYears: months === null
        ? ''
        : formatCalculatedValue(months / 12),
    }))
  }

  const updateGracePeriodYears = (value: string) => {
    const years = numberValue(value)
    setFormState((current) => ({
      ...current,
      gracePeriodTermYears: value,
      gracePeriodTermMonths: years === null
        ? ''
        : String(Math.round(years * 12)),
    }))
  }

  const updateGracePeriodMonths = (value: string) => {
    const months = numberValue(value)
    setFormState((current) => ({
      ...current,
      gracePeriodTermMonths: value,
      gracePeriodTermYears: months === null
        ? ''
        : formatCalculatedValue(months / 12),
    }))
  }

  const updateInitialPaymentDate = (value: string) => {
    resetActiveErrors()
    setFormState((current) => ({
      ...current,
      initialPaymentDate: value,
      trenches: current.trenches.map((trench, index) => (
        index === 0
        && (!trench.date || trench.date === current.initialPaymentDate)
          ? { ...trench, date: value }
          : trench
      )),
    }))
  }

  const updateAnnualRate = (value: string) => {
    resetActiveErrors()
    setFormState((current) => ({
      ...current,
      annualRate: value,
      trenches: current.trenches.map((trench) => (
        !trench.annualRate || trench.annualRate === current.annualRate
          ? { ...trench, annualRate: value }
          : trench
      )),
    }))
  }

  const updateTrench = <FieldName extends keyof TrenchRowState>(
    trenchIndex: number,
    fieldName: FieldName,
    value: TrenchRowState[FieldName],
  ) => {
    resetActiveErrors()
    setFormState((current) => ({
      ...current,
      trenches: current.trenches.map((trench, index) => (
        index === trenchIndex
          ? { ...trench, [fieldName]: value }
          : trench
      )),
    }))
  }

  const updateTrenchAmount = (
    trenchIndex: number,
    source: ValueSource,
    value: string,
  ) => {
    resetActiveErrors()
    setFormState((current) => synchronizeMoneyFields({
      ...current,
      trenches: current.trenches.map((trench, index) => (
        index === trenchIndex
          ? {
              ...trench,
              amountSource: source,
              ...(source === 'percent'
                ? { amountPercent: value }
                : { amountRubles: value }),
            }
          : trench
      )),
    }))
  }

  const selectProgram = (programIdentifier: string) => {
    const program = optionsQuery.data?.programs.find(
      (item) => String(item.id) === programIdentifier,
    )
    if (!program) {
      updateField('bankProgramId', '')
      return
    }
    setFormState((current) => {
      const maximumTermMonths = program.maximumLoanTermYears
        ? Math.min(
            Number(current.mortgageTermMonths),
            program.maximumLoanTermYears * 12,
          )
        : Number(current.mortgageTermMonths)
      const minimumInitialPayment = Math.max(
        Number(current.initialPaymentPercent),
        Number(program.minimumInitialPaymentPercent),
      )
      return synchronizeMoneyFields({
        ...current,
        bankProgramId: programIdentifier,
        annualRate: program.interestRate,
        mortgageTermMonths: String(maximumTermMonths),
        mortgageTermYears: formatCalculatedValue(maximumTermMonths / 12),
        initialPaymentSource: 'percent',
        initialPaymentPercent: String(minimumInitialPayment),
        trenches: current.trenches.map((trench) => ({
          ...trench,
          annualRate: program.interestRate,
        })),
      })
    })
  }

  const changeCalculationType = (value: CalculationType) => {
    setCalculationType(value)
    marketCalculationMutation.reset()
    trenchCalculationMutation.reset()
    marketSaveMutation.reset()
    trenchSaveMutation.reset()
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    activeSaveMutation.reset()
    if (calculationType === 'market') {
      marketCalculationMutation.mutate(
        buildMarketPayload(formState, initialPaymentDate),
      )
    } else {
      trenchCalculationMutation.mutate(
        buildTrenchPayload(formState, initialPaymentDate),
      )
    }
  }

  const generalError = fieldErrors.nonFieldErrors
    ?? (activeCalculationMutation.isError
      && Object.keys(fieldErrors).length === 0
      ? 'Не удалось выполнить расчёт. Проверьте данные и повторите попытку.'
      : null)
  const resultAction = (
    <section
      className="save-calculation-panel"
      aria-label="Сохранение расчёта"
    >
      <div>
        <span className="eyebrow">История расчётов</span>
        <h2>Сохранить этот сценарий</h2>
        {!sessionQuery.data?.isAuthenticated ? (
          <p>Войдите в аккаунт, чтобы сохранить расчёт.</p>
        ) : selectedPropertyIdentifier ? (
          <p>
            Расчёт будет связан с выбранным объектом
            {customerIdentifier ? ' и карточкой клиента' : ''}.
          </p>
        ) : (
          <p>Для сохранения выберите объект в блоке «Данные объекта».</p>
        )}
        {activeSaveMutation.isError ? (
          <p className="save-calculation-panel__error" role="alert">
            Не удалось сохранить расчёт. Повторите попытку.
          </p>
        ) : null}
      </div>
      <div className="save-calculation-panel__actions">
        {!sessionQuery.data?.isAuthenticated ? (
          <a
            className="button button--primary"
            href={`/app/login?next=${encodeURIComponent(loginReturnPath)}`}
          >
            Войти
          </a>
        ) : selectedPropertyIdentifier ? (
          activeSaveMutation.data && customerIdentifier ? (
            <Link className="button button--primary" to={`/customers/${customerIdentifier}`}>
              Открыть карточку клиента
            </Link>
          ) : activeSaveMutation.data ? (
            <Link
              className="button button--primary"
              to={calculationType === 'market'
                ? `/mortgage/calculations/${activeSaveMutation.data.id}`
                : `/mortgage/trench/calculations/${activeSaveMutation.data.id}`}
            >
              Открыть сохранённый расчёт
            </Link>
          ) : (
            <button
              className="button button--primary"
              type="button"
              disabled={activeSaveMutation.isPending}
              onClick={() => {
                if (calculationType === 'market'
                  && marketCalculationMutation.variables) {
                  marketSaveMutation.mutate({
                    propertyId: selectedPropertyIdentifier,
                    parameters: marketCalculationMutation.variables,
                    ...(customerIdentifier
                      ? { customerId: customerIdentifier }
                      : {}),
                  })
                }
                if (calculationType === 'trench'
                  && trenchCalculationMutation.variables) {
                  trenchSaveMutation.mutate({
                    propertyId: selectedPropertyIdentifier,
                    parameters: trenchCalculationMutation.variables,
                    ...(customerIdentifier
                      ? { customerId: customerIdentifier }
                      : {}),
                  })
                }
              }}
            >
              {activeSaveMutation.isPending ? 'Сохраняем…' : 'Сохранить расчёт'}
            </button>
          )
        ) : (
          <Link className="button button--secondary" to="/properties">
            Выбрать объект
          </Link>
        )}
      </div>
    </section>
  )

  return (
    <div className="page-stack mortgage-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Финансовая модель</span>
          <h1>Ипотечный калькулятор</h1>
          <p>
            Рыночная и траншевая ипотека в одной форме с общими данными
            объекта и условиями кредита.
          </p>
        </div>
        <div className="page-header__actions">
          <a className="button button--secondary" href="/mortgage/">
            Django-версия
          </a>
        </div>
      </header>

      {sampleIdentifier && !sessionQuery.data?.isAuthenticated ? (
        <p className="status-notice" role="status">
          Войдите в аккаунт, чтобы загрузить параметры сохранённого расчёта.
        </p>
      ) : null}
      {activeSampleQuery.isLoading ? (
        <p className="status-notice" role="status">
          Загружаем параметры сохранённого расчёта…
        </p>
      ) : null}
      {activeSampleQuery.isError ? (
        <p className="form-error" role="alert">
          Сохранённый расчёт не найден или недоступен. Можно заполнить форму
          вручную.
        </p>
      ) : null}

      <div className="mortgage-layout">
        <form className="calculator-card" noValidate onSubmit={handleSubmit}>
          <section className="calculator-section" aria-labelledby="property-data-heading">
            <div className="calculator-section__heading calculator-section__heading--actions">
              <span>01</span>
              <div>
                <h2 id="property-data-heading">Данные объекта</h2>
                <p>Выберите объект из каталога или заполните данные вручную</p>
              </div>
              <button
                className="text-button calculator-section__clear"
                type="button"
                onClick={() => {
                  setSelectedPropertyIdentifier(null)
                  setPropertyData(EMPTY_PROPERTY_DATA)
                }}
              >
                Очистить поля
              </button>
            </div>
            <div className="field-grid property-data-grid">
              <label className="form-field form-field--wide">
                <span>Объект недвижимости</span>
                <select
                  value={selectedPropertyIdentifier ?? ''}
                  disabled={propertyListQuery.isLoading}
                  onChange={(event) => selectProperty(event.target.value)}
                >
                  <option value="">Не выбран — ручное заполнение</option>
                  {propertyItems.map((property) => (
                    <option value={property.id} key={property.id}>
                      {property.city}, {property.realEstateComplex}, корпус {property.building}, кв. {property.apartmentNumber}
                    </option>
                  ))}
                </select>
                {propertyListQuery.isError ? (
                  <small role="status">Каталог временно недоступен; поля можно заполнить вручную.</small>
                ) : null}
              </label>
              {([
                ['city', 'Город'],
                ['district', 'Район'],
                ['developer', 'Застройщик'],
                ['realEstateComplex', 'Жилой комплекс'],
                ['building', 'Корпус'],
                ['apartmentNumber', 'Номер квартиры'],
                ['area', 'Площадь, м²'],
                ['layout', 'Планировка'],
                ['floor', 'Этаж'],
                ['decoration', 'Отделка'],
              ] as const).map(([fieldName, label]) => (
                <label className="form-field" key={fieldName}>
                  <span>{label}</span>
                  <input
                    type={fieldName === 'area' || fieldName === 'floor' ? 'number' : 'text'}
                    step={fieldName === 'area' ? '0.01' : undefined}
                    value={propertyData[fieldName]}
                    onChange={(event) => updatePropertyData(fieldName, event.target.value)}
                  />
                </label>
              ))}
            </div>
          </section>

          <section className="calculator-section" aria-labelledby="object-cost-heading">
            <div className="calculator-section__heading">
              <span>02</span>
              <div>
                <h2 id="object-cost-heading">Стоимость объекта</h2>
                <p>Цена и синхронная корректировка в процентах и рублях</p>
              </div>
            </div>
            <div className="field-grid">
              <label className="form-field form-field--wide">
                <span>Базовая стоимость, ₽</span>
                <input
                  name="propertyCost"
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                  value={formState.propertyCost}
                  aria-invalid={Boolean(fieldErrors.propertyCost)}
                  aria-describedby={fieldErrors.propertyCost ? 'propertyCost-error' : undefined}
                  onChange={(event) => updatePropertyCost(event.target.value)}
                />
                <FieldError fieldName="propertyCost" errors={fieldErrors} />
              </label>
              <fieldset className="form-field form-field--wide segmented-field">
                <legend>Тип корректировки</legend>
                <div className="segmented-control">
                  <label>
                    <input
                      name="priceAdjustmentType"
                      type="radio"
                      checked={formState.priceAdjustmentType === 'discount'}
                      onChange={() => setFormState((current) => synchronizeMoneyFields({ ...current, priceAdjustmentType: 'discount' }))}
                    />
                    Скидка
                  </label>
                  <label>
                    <input
                      name="priceAdjustmentType"
                      type="radio"
                      checked={formState.priceAdjustmentType === 'markup'}
                      onChange={() => setFormState((current) => synchronizeMoneyFields({ ...current, priceAdjustmentType: 'markup' }))}
                    />
                    Удорожание
                  </label>
                </div>
              </fieldset>
              <label className="form-field">
                <span>{formState.priceAdjustmentType === 'discount' ? 'Скидка, %' : 'Удорожание, %'}</span>
                <input
                  aria-label={formState.priceAdjustmentType === 'discount' ? 'Скидка, %' : 'Удорожание, %'}
                  type="number"
                  min="0"
                  step="0.01"
                  required
                  value={formState.priceAdjustmentPercent}
                  aria-invalid={Boolean(fieldErrors.priceAdjustmentValue)}
                  onChange={(event) => updateAdjustment('percent', event.target.value)}
                />
                <small>{formState.priceAdjustmentSource === 'percent' ? 'Изменяемое значение' : 'Рассчитывается автоматически'}</small>
              </label>
              <label className="form-field">
                <span>{formState.priceAdjustmentType === 'discount' ? 'Скидка, ₽' : 'Удорожание, ₽'}</span>
                <input
                  aria-label={formState.priceAdjustmentType === 'discount' ? 'Скидка, ₽' : 'Удорожание, ₽'}
                  type="number"
                  min="0"
                  step="0.01"
                  required
                  value={formState.priceAdjustmentRubles}
                  aria-invalid={Boolean(fieldErrors.priceAdjustmentValue)}
                  onChange={(event) => updateAdjustment('rubles', event.target.value)}
                />
                <small>{formState.priceAdjustmentSource === 'rubles' ? 'Изменяемое значение' : 'Рассчитывается автоматически'}</small>
                <FieldError fieldName="priceAdjustmentValue" errors={fieldErrors} />
              </label>
              <div className="calculated-value form-field--wide" role="status">
                <span>Итоговая стоимость объекта</span>
                <strong>{formatCalculatedValue(finalPropertyCost)} ₽</strong>
              </div>
            </div>
          </section>

          <section className="calculator-section" aria-labelledby="loan-parameters-heading">
            <div className="calculator-section__heading">
              <span>03</span>
              <div>
                <h2 id="loan-parameters-heading">Условия кредита</h2>
                <p>Программа, взнос, срок и ставка</p>
              </div>
            </div>
            <div className="field-grid">
              <label className="form-field">
                <span>Банк</span>
                <select
                  value={formState.bankId}
                  disabled={optionsQuery.isLoading}
                  onChange={(event) => setFormState((current) => ({
                    ...current,
                    bankId: event.target.value,
                    bankProgramId: '',
                  }))}
                >
                  <option value="">Без выбора</option>
                  {optionsQuery.data?.banks.map((bank) => (
                    <option value={bank.id} key={bank.id}>{bank.name}</option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                <span>Ипотечная программа</span>
                <select
                  value={formState.bankProgramId}
                  disabled={!formState.bankId}
                  onChange={(event) => selectProgram(event.target.value)}
                >
                  <option value="">Ручные параметры</option>
                  {availablePrograms.map((program) => (
                    <option value={program.id} key={program.id}>
                      {program.programName} — {formatPercent(program.interestRate)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                <span>Первоначальный взнос, %</span>
                <input
                  aria-label="Первоначальный взнос, %"
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  required
                  value={formState.initialPaymentPercent}
                  aria-invalid={Boolean(fieldErrors.initialPaymentValue)}
                  onChange={(event) => updateInitialPayment('percent', event.target.value)}
                />
                <small>{formState.initialPaymentSource === 'percent' ? 'Изменяемое значение' : 'Рассчитывается автоматически'}</small>
              </label>
              <label className="form-field">
                <span>Первоначальный взнос, ₽</span>
                <input
                  aria-label="Первоначальный взнос, ₽"
                  type="number"
                  min="0"
                  step="0.01"
                  required
                  value={formState.initialPaymentRubles}
                  aria-invalid={Boolean(fieldErrors.initialPaymentValue)}
                  onChange={(event) => updateInitialPayment('rubles', event.target.value)}
                />
                <small>{formState.initialPaymentSource === 'rubles' ? 'Изменяемое значение' : 'Рассчитывается автоматически'}</small>
                <FieldError fieldName="initialPaymentValue" errors={fieldErrors} />
              </label>
              <label className="form-field form-field--wide">
                <span>Дата первоначального взноса</span>
                <input
                  type="date"
                  required
                  value={initialPaymentDate}
                  aria-invalid={Boolean(fieldErrors.initialPaymentDate)}
                  aria-describedby={fieldErrors.initialPaymentDate ? 'initialPaymentDate-error' : undefined}
                  onChange={(event) => updateInitialPaymentDate(event.target.value)}
                />
                <FieldError fieldName="initialPaymentDate" errors={fieldErrors} />
              </label>
              <label className="form-field">
                <span>Срок ипотеки, лет</span>
                <input
                  type="number"
                  min="0.01"
                  max="50"
                  step="0.01"
                  required
                  value={formState.mortgageTermYears}
                  onChange={(event) => updateMortgageTermYears(event.target.value)}
                />
              </label>
              <label className="form-field">
                <span>Срок ипотеки, месяцев</span>
                <input
                  type="number"
                  min="1"
                  max="600"
                  step="1"
                  required
                  value={formState.mortgageTermMonths}
                  aria-invalid={Boolean(fieldErrors.mortgageTermMonths)}
                  aria-describedby={fieldErrors.mortgageTermMonths ? 'mortgageTermMonths-error' : undefined}
                  onChange={(event) => updateMortgageTermMonths(event.target.value)}
                />
                <FieldError fieldName="mortgageTermMonths" errors={fieldErrors} />
              </label>
              <label className="form-field form-field--wide">
                <span>Годовая ставка, %</span>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  required
                  value={formState.annualRate}
                  aria-invalid={Boolean(fieldErrors.annualRate)}
                  aria-describedby={fieldErrors.annualRate ? 'annualRate-error' : undefined}
                  onChange={(event) => updateAnnualRate(event.target.value)}
                />
                <FieldError fieldName="annualRate" errors={fieldErrors} />
              </label>
            </div>
          </section>

          <section className="calculator-section" aria-labelledby="calculation-type-heading">
            <div className="calculator-section__heading">
              <span>04</span>
              <div>
                <h2 id="calculation-type-heading">Вариант расчёта</h2>
                <p>Общие данные выше сохраняются при переключении режима</p>
              </div>
            </div>
            <fieldset className="form-field segmented-field calculation-type-field">
              <legend className="visually-hidden">Вариант ипотеки</legend>
              <div className="segmented-control">
                <label>
                  <input
                    name="calculationType"
                    type="radio"
                    checked={calculationType === 'market'}
                    onChange={() => changeCalculationType('market')}
                  />
                  Рыночная ипотека
                </label>
                <label>
                  <input
                    name="calculationType"
                    type="radio"
                    checked={calculationType === 'trench'}
                    onChange={() => changeCalculationType('trench')}
                  />
                  Траншевая ипотека
                </label>
              </div>
            </fieldset>

            {calculationType === 'market' ? (
              <div className="calculation-variant-fields">
                <label className="toggle-field">
                  <input
                    type="checkbox"
                    checked={formState.hasGracePeriod}
                    onChange={(event) => updateField('hasGracePeriod', event.target.checked)}
                  />
                  <span>Использовать льготный период</span>
                </label>
                {formState.hasGracePeriod ? (
                  <div className="field-grid grace-fields">
                    <label className="form-field">
                      <span>Льготный период, лет</span>
                      <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        required
                        value={formState.gracePeriodTermYears}
                        onChange={(event) => updateGracePeriodYears(event.target.value)}
                      />
                    </label>
                    <label className="form-field">
                      <span>Льготный период, месяцев</span>
                      <input
                        type="number"
                        min="1"
                        max="599"
                        required
                        value={formState.gracePeriodTermMonths}
                        aria-invalid={Boolean(fieldErrors.gracePeriodTermMonths)}
                        onChange={(event) => updateGracePeriodMonths(event.target.value)}
                      />
                      <FieldError fieldName="gracePeriodTermMonths" errors={fieldErrors} />
                    </label>
                    <label className="form-field form-field--wide">
                      <span>Ставка льготного периода, %</span>
                      <input
                        type="number"
                        min="0.01"
                        max="100"
                        step="0.01"
                        required
                        value={formState.gracePeriodRate}
                        aria-invalid={Boolean(fieldErrors.gracePeriodRate)}
                        onChange={(event) => updateField('gracePeriodRate', event.target.value)}
                      />
                      <FieldError fieldName="gracePeriodRate" errors={fieldErrors} />
                    </label>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="calculation-variant-fields">
                <label className="form-field trench-count-field">
                  <span>Количество траншей</span>
                  <select
                    value={formState.trenchCount}
                    onChange={(event) => updateField('trenchCount', Number(event.target.value))}
                  >
                    {[1, 2, 3, 4, 5].map((count) => (
                      <option value={count} key={count}>{count}</option>
                    ))}
                  </select>
                </label>
                <div className="trench-input-list">
                  {formState.trenches.slice(0, formState.trenchCount).map((trench, index) => {
                    const isLast = index === formState.trenchCount - 1
                    const usedPercent = formState.trenches
                      .slice(0, index)
                      .reduce((sum, item) => sum + (numberValue(item.amountPercent) ?? 0), 0)
                    const usedRubles = formState.trenches
                      .slice(0, index)
                      .reduce((sum, item) => sum + (numberValue(item.amountRubles) ?? 0), 0)
                    const remainderPercent = Math.max(0, 100 - usedPercent)
                    const remainderRubles = Math.max(0, loanAmount - usedRubles)
                    const dateFieldName = `trenches.${index}.date`
                    const amountFieldName = `trenches.${index}.amountValue`
                    const rateFieldName = `trenches.${index}.annualRate`
                    return (
                      <fieldset className="trench-input-card" key={index}>
                        <legend>
                          Транш {index + 1}
                          {isLast ? <small>остаточный</small> : null}
                        </legend>
                        <div className="field-grid trench-input-grid">
                          <label className="form-field">
                            <span>Дата транша</span>
                            <input
                              type="date"
                              required
                              value={trench.date || (index === 0 ? initialPaymentDate : '')}
                              aria-invalid={Boolean(fieldErrors[dateFieldName])}
                              onChange={(event) => updateTrench(index, 'date', event.target.value)}
                            />
                            <FieldError fieldName={dateFieldName} errors={fieldErrors} />
                          </label>
                          <label className="form-field">
                            <span>Сумма транша, %</span>
                            <input
                              aria-label="Сумма транша, %"
                              type="number"
                              min="0"
                              max="100"
                              step="0.01"
                              required
                              readOnly={isLast}
                              value={isLast ? formatCalculatedValue(remainderPercent) : trench.amountPercent}
                              aria-invalid={Boolean(fieldErrors[amountFieldName])}
                              onChange={(event) => updateTrenchAmount(index, 'percent', event.target.value)}
                            />
                            {!isLast ? <small>{trench.amountSource === 'percent' ? 'Изменяемое значение' : 'Рассчитывается автоматически'}</small> : null}
                          </label>
                          <label className="form-field">
                            <span>Сумма транша, ₽</span>
                            <input
                              aria-label="Сумма транша, ₽"
                              type="number"
                              min="0"
                              step="0.01"
                              required
                              readOnly={isLast}
                              value={isLast ? formatCalculatedValue(remainderRubles) : trench.amountRubles}
                              aria-invalid={Boolean(fieldErrors[amountFieldName])}
                              onChange={(event) => updateTrenchAmount(index, 'rubles', event.target.value)}
                            />
                            {!isLast ? <small>{trench.amountSource === 'rubles' ? 'Изменяемое значение' : 'Рассчитывается автоматически'}</small> : null}
                            <FieldError fieldName={amountFieldName} errors={fieldErrors} />
                          </label>
                          <label className="form-field">
                            <span>Годовая ставка, %</span>
                            <input
                              type="number"
                              min="0"
                              max="100"
                              step="0.01"
                              required
                              value={trench.annualRate}
                              aria-invalid={Boolean(fieldErrors[rateFieldName])}
                              onChange={(event) => updateTrench(index, 'annualRate', event.target.value)}
                            />
                            <FieldError fieldName={rateFieldName} errors={fieldErrors} />
                          </label>
                        </div>
                      </fieldset>
                    )
                  })}
                </div>
              </div>
            )}
          </section>

          {generalError ? <p className="form-error" role="alert">{generalError}</p> : null}
          <button
            className="button button--primary calculator-submit"
            type="submit"
            disabled={activeCalculationMutation.isPending}
          >
            {activeCalculationMutation.isPending
              ? 'Рассчитываем…'
              : calculationType === 'market'
                ? 'Рассчитать ипотеку'
                : 'Рассчитать траншевую ипотеку'}
          </button>
        </form>

        <aside className="calculator-reference" aria-label="Справочная информация">
          <span className="eyebrow">Ориентир</span>
          <strong>{optionsQuery.data ? formatPercent(optionsQuery.data.keyRate) : '—'}</strong>
          <p>Актуальная ключевая ставка из справочника приложения.</p>
          {optionsQuery.isError ? (
            <p className="reference-warning" role="status">
              Программы банков временно недоступны. Ручной расчёт продолжает работать.
            </p>
          ) : null}
          <Link to={calculationType === 'market'
            ? '/mortgage/calculations'
            : '/mortgage/trench/calculations'}>
            История расчётов <span aria-hidden="true">→</span>
          </Link>
        </aside>
      </div>

      <div aria-live="polite">
        <ResultRegion
          calculationType={calculationType}
          marketResult={marketCalculationMutation.data}
          trenchResult={trenchCalculationMutation.data}
          marketResultHeadingRef={marketResultHeadingRef}
          trenchResultHeadingRef={trenchResultHeadingRef}
          action={resultAction}
        />
      </div>
    </div>
  )
}
